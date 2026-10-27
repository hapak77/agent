"""Shared pytest fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio

# Ensure test env before settings import
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LLM_USE_MOCK", "true")
os.environ.setdefault("OUTREACH_ENABLED", "true")
os.environ.setdefault("OUTREACH_DRY_RUN", "false")
os.environ.setdefault("SOURCE_FIXTURE_ENABLED", "true")
os.environ.setdefault("SOURCE_RSS_ENABLED", "false")
os.environ.setdefault("SOURCE_TELEGRAM_ENABLED", "false")
os.environ.setdefault("SOURCE_KWORK_ENABLED", "false")
os.environ.setdefault("SOURCE_FLRU_ENABLED", "false")
os.environ.setdefault("OWNER_TELEGRAM_ID", "1")

from freelance_radar.config import Settings, clear_settings_cache  # noqa: E402
from freelance_radar.db.session import dispose_db, init_db, reset_engine, session_scope  # noqa: E402
from freelance_radar.llm.mock import MockLLMClient  # noqa: E402
from freelance_radar.outreach.adapters.mock import MockOutreachAdapter  # noqa: E402
from freelance_radar.outreach.service import OutreachService  # noqa: E402
from freelance_radar.pipeline.runner import PipelineRunner  # noqa: E402
from freelance_radar.sources.fixture import FixtureSourceAdapter  # noqa: E402


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "data" / "fixture_orders.json"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    clear_settings_cache()
    db_path = tmp_path / "test.db"
    s = Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{db_path}",
        llm_use_mock=True,
        outreach_enabled=True,
        outreach_dry_run=False,
        outreach_min_interval_seconds=0,
        outreach_max_per_hour=100,
        outreach_max_per_day=100,
        source_fixture_enabled=True,
        source_rss_enabled=False,
        source_telegram_enabled=False,
        source_kwork_enabled=False,
        source_flru_enabled=False,
        fixture_orders_path=str(FIXTURE_PATH),
        owner_telegram_id=1,
        telegram_bot_token="",
        collect_interval_seconds=60,
        pipeline_batch_size=50,
    )
    return s


@pytest_asyncio.fixture
async def db(settings: Settings):
    reset_engine()
    await init_db(settings)
    yield
    await dispose_db()
    reset_engine()


@pytest.fixture
def llm() -> MockLLMClient:
    return MockLLMClient()


@pytest.fixture
def mock_outreach() -> MockOutreachAdapter:
    return MockOutreachAdapter()


@pytest.fixture
def pipeline(settings: Settings, llm: MockLLMClient) -> PipelineRunner:
    adapter = FixtureSourceAdapter(settings.fixture_orders_path)
    return PipelineRunner(settings=settings, adapters=[adapter], llm=llm)


@pytest.fixture
def outreach_service(settings: Settings, mock_outreach: MockOutreachAdapter) -> OutreachService:
    notifications: list[str] = []

    async def notify(text: str) -> None:
        notifications.append(text)

    service = OutreachService(
        settings=settings,
        adapters={"mock": mock_outreach, "telegram": mock_outreach},
        notify=notify,
    )
    service._notifications = notifications  # type: ignore[attr-defined]
    return service


@pytest_asyncio.fixture
async def seeded_pipeline(db, pipeline: PipelineRunner):
    await pipeline.register_sources()
    await pipeline.run_once()
    return pipeline
