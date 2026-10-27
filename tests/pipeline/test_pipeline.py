"""Full pipeline tests with fixture source."""

import pytest
from sqlalchemy import select

from freelance_radar.db import repositories as repo
from freelance_radar.db.models import Order, OrderStatus
from freelance_radar.db.session import session_scope


@pytest.mark.asyncio
async def test_pipeline_ingests_and_classifies(db, pipeline):
    await pipeline.register_sources()
    result = await pipeline.run_once()
    assert result["processed"] >= 1

    async with session_scope() as session:
        orders = (await session.execute(select(Order))).scalars().all()
        assert len(orders) >= 8

        # Exact duplicate archived
        dups = [o for o in orders if o.is_duplicate]
        assert dups, "expected exact duplicate from fixture"

        # No invented budget — RAG order without amount
        unknown = next(o for o in orders if "не обсуждали" in (o.raw_text or "").lower())
        assert unknown.budget_unknown is True
        assert unknown.budget_amount is None

        # Spam / hard block rejected or low
        spam = next(o for o in orders if "казино" in (o.raw_text or "").lower())
        assert spam.status in {OrderStatus.rejected, OrderStatus.archived}

        # Real order ready
        real = next(o for o in orders if "REST API" in (o.raw_text or "") and not o.is_duplicate)
        assert real.status == OrderStatus.ready_for_outreach
        assert real.priority_score and real.priority_score >= 3

        # Unknown author → manual
        anon = next(o for o in orders if "лендинг" in (o.raw_text or "").lower())
        assert anon.contact_status.value == "manual_contact_required"
        assert anon.contact_message
        assert "актуален" in anon.contact_message


@pytest.mark.asyncio
async def test_rerun_is_idempotent(db, pipeline):
    await pipeline.register_sources()
    first = await pipeline.run_once()
    second = await pipeline.collect_all()
    # Second collect should not create new non-dup orders
    assert second["fixture"]["created"] == 0

    async with session_scope() as session:
        stats = await repo.get_stats(session)
        assert stats["orders_total"] >= first["processed"]


@pytest.mark.asyncio
async def test_pause_stops_pipeline(db, pipeline):
    await pipeline.register_sources()
    async with session_scope() as session:
        await repo.set_app_flag(session, "pipeline_paused", True)
    result = await pipeline.run_once()
    assert result["collected"] == {}
    assert result["processed"] == 0
