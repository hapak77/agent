"""Rate limit enforcement for outreach."""

import pytest

from freelance_radar.db import repositories as repo
from freelance_radar.db.models import ContactStatus, OrderStatus
from freelance_radar.db.session import session_scope
from freelance_radar.outreach.adapters.mock import MockOutreachAdapter
from freelance_radar.outreach.service import OutreachService


@pytest.mark.asyncio
async def test_hourly_limit_pauses(db, pipeline, settings):
    settings.outreach_max_per_hour = 1
    settings.outreach_min_interval_seconds = 0
    await pipeline.register_sources()
    await pipeline.run_once()

    mock = MockOutreachAdapter()
    service = OutreachService(
        settings=settings,
        adapters={"mock": mock, "telegram": mock},
    )
    first = await service.process_queue(limit=1)
    assert any(o.get("action") == "sent" for o in first)
    second = await service.process_queue(limit=5)
    assert any(o.get("action") == "pause" and o.get("reason") == "hourly_limit" for o in second) or second == []
    # If candidates remain, pause reason should appear
    async with session_scope() as session:
        ready = await repo.list_outreach_candidates(session, limit=10)
        if ready:
            assert any(o.get("action") == "pause" for o in second)
