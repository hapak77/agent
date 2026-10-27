"""Wire application services."""

from __future__ import annotations

from freelance_radar.bot.app import OwnerNotifier, create_bot
from freelance_radar.config import Settings
from freelance_radar.llm.factory import build_llm_client
from freelance_radar.outreach.adapters.mock import MockOutreachAdapter
from freelance_radar.outreach.adapters.telegram_dm import TelegramDMAdapter
from freelance_radar.outreach.service import OutreachService
from freelance_radar.pipeline.runner import PipelineRunner
from freelance_radar.sources.registry import build_adapters


def build_pipeline(settings: Settings) -> PipelineRunner:
    return PipelineRunner(
        settings=settings,
        adapters=build_adapters(settings),
        llm=build_llm_client(settings),
    )


def build_outreach(settings: Settings, notifier: OwnerNotifier | None = None) -> OutreachService:
    adapters = {
        "mock": MockOutreachAdapter(),
        "telegram": TelegramDMAdapter(
            api_id=settings.telegram_api_id,
            api_hash=settings.telegram_api_hash,
            session_path=settings.telegram_session_path,
            dry_run=settings.outreach_dry_run or not settings.outreach_enabled,
        ),
    }
    # In dry-run / disabled mode, prefer mock for fake recipients in tests;
    # live telegram adapter still reports DRY_RUN without claiming success.
    return OutreachService(
        settings=settings,
        adapters=adapters,
        notify=notifier,
    )


def build_notifier(settings: Settings) -> OwnerNotifier:
    bot = create_bot(settings)
    return OwnerNotifier(bot, settings.owner_telegram_id)
