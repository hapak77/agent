"""Outreach tests with mock adapters only."""

import pytest

from freelance_radar.db import repositories as repo
from freelance_radar.db.models import ContactStatus, OrderStatus
from freelance_radar.db.session import session_scope
from freelance_radar.outreach.adapters.mock import MockOutreachAdapter
from freelance_radar.outreach.service import OutreachService


@pytest.mark.asyncio
async def test_successful_send_confirmed(db, pipeline, settings):
    await pipeline.register_sources()
    await pipeline.run_once()

    mock = MockOutreachAdapter()
    notes: list[str] = []

    async def notify(t: str) -> None:
        notes.append(t)

    service = OutreachService(
        settings=settings,
        adapters={"mock": mock, "telegram": mock},
        notify=notify,
    )
    outcomes = await service.process_queue(limit=20)
    sent = [o for o in outcomes if o.get("action") == "sent"]
    assert sent, outcomes
    assert any("подтверждено" in n.lower() or "отправлен" in n.lower() for n in notes)
    # Never claim success without confirmation — mock confirms
    assert all(o.get("confirmed") for o in sent)
    assert mock.sent


@pytest.mark.asyncio
async def test_send_failure_not_reported_as_success(db, pipeline, settings):
    await pipeline.register_sources()
    await pipeline.run_once()

    # Force fail recipient on fx-009 style
    mock = MockOutreachAdapter(fail_recipients={"fail:1009", "1009"})
    notes: list[str] = []

    async def notify(t: str) -> None:
        notes.append(t)

    # Mark only the fail order ready and queue it
    async with session_scope() as session:
        orders = await repo.list_orders(session, limit=50)
        target = next(o for o in orders if "Excel" in (o.raw_text or "") or "excel" in (o.raw_text or "").lower())
        target.status = OrderStatus.ready_for_outreach
        target.contact_status = ContactStatus.queued
        target.contact_message = "Здравствуйте! Я по поводу вашего заказа: Excel отчёт. Подскажите, пожалуйста, он ещё актуален?"
        target.author_contact = "fail:1009"
        # Prevent other sends in this test
        for o in orders:
            if o.id != target.id and o.status == OrderStatus.ready_for_outreach:
                o.contact_status = ContactStatus.skipped

    service = OutreachService(
        settings=settings,
        adapters={"mock": mock, "telegram": mock},
        notify=notify,
    )
    outcomes = await service.process_queue(limit=5)
    assert any(o.get("action") == "failed" for o in outcomes)
    assert any("не удалась" in n.lower() or "не подтверждена" in n.lower() for n in notes)
    assert not any("✅" in n and "подтверждено" in n.lower() for n in notes if "не" in n.lower())


@pytest.mark.asyncio
async def test_unknown_author_manual(db, pipeline, settings, outreach_service):
    await pipeline.register_sources()
    await pipeline.run_once()
    outcomes = await outreach_service.process_queue(limit=30)
    manuals = [o for o in outcomes if o.get("action") == "manual"]
    assert manuals
    notes = outreach_service._notifications  # type: ignore[attr-defined]
    assert any("ручной контакт" in n.lower() for n in notes)


@pytest.mark.asyncio
async def test_no_duplicate_contact(db, pipeline, settings):
    await pipeline.register_sources()
    await pipeline.run_once()
    mock = MockOutreachAdapter()
    service = OutreachService(
        settings=settings,
        adapters={"mock": mock, "telegram": mock},
        notify=None,
    )
    await service.process_queue(limit=50)
    first_count = len(mock.sent)
    await service.process_queue(limit=50)
    # Should not double-send to same recipients for same orders
    assert len(mock.sent) == first_count


@pytest.mark.asyncio
async def test_stop_outreach_flag(db, pipeline, settings):
    await pipeline.register_sources()
    await pipeline.run_once()
    async with session_scope() as session:
        await repo.set_app_flag(session, "outreach_stopped", True)
    mock = MockOutreachAdapter()
    service = OutreachService(
        settings=settings,
        adapters={"mock": mock, "telegram": mock},
    )
    outcomes = await service.process_queue(limit=10)
    assert outcomes == []
    assert mock.sent == []


@pytest.mark.asyncio
async def test_floodwait_pauses(db, pipeline, settings):
    await pipeline.register_sources()
    await pipeline.run_once()
    mock = MockOutreachAdapter(flood_wait=True)
    notes: list[str] = []

    async def notify(t: str) -> None:
        notes.append(t)

    service = OutreachService(
        settings=settings,
        adapters={"mock": mock, "telegram": mock},
        notify=notify,
    )
    outcomes = await service.process_queue(limit=3)
    assert any(o.get("action") == "pause" for o in outcomes)
    async with session_scope() as session:
        stopped = await repo.get_app_flag(session, "outreach_stopped", False)
        assert stopped is True
