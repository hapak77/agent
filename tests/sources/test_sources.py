"""Source adapter probes and fixture collect."""

import pytest

from freelance_radar.sources.fixture import FixtureSourceAdapter
from freelance_radar.sources.flru import FLruSourceAdapter
from freelance_radar.sources.kwork import KworkSourceAdapter
from freelance_radar.sources.rss import RSSSourceAdapter
from freelance_radar.sources.telegram_channels import TelegramChannelsAdapter
from tests.conftest import FIXTURE_PATH


@pytest.mark.asyncio
async def test_fixture_probe_and_collect():
    adapter = FixtureSourceAdapter(FIXTURE_PATH)
    caps = await adapter.probe()
    assert caps.available
    assert caps.can_auto_contact is False
    result = await adapter.collect()
    assert len(result.listings) >= 5
    assert not result.errors


@pytest.mark.asyncio
async def test_rss_without_urls_unavailable():
    adapter = RSSSourceAdapter([])
    caps = await adapter.probe()
    assert caps.available is False
    assert caps.alternatives


@pytest.mark.asyncio
async def test_telegram_without_creds_reports_limitation():
    adapter = TelegramChannelsAdapter(
        api_id=None, api_hash="", session_path="./data/missing.session", channels=[]
    )
    caps = await adapter.probe()
    assert caps.available is False
    assert "bot" in (caps.notes or "").lower() or caps.unavailable_reason


@pytest.mark.asyncio
async def test_kwork_stub_does_not_fake_listings():
    adapter = KworkSourceAdapter()
    caps = await adapter.probe()
    assert caps.can_read is False
    result = await adapter.collect()
    assert result.listings == []
    assert result.errors


@pytest.mark.asyncio
async def test_flru_stub_does_not_fake_listings():
    adapter = FLruSourceAdapter()
    result = await adapter.collect()
    assert result.listings == []
