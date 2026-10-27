"""Build enabled source adapters from settings."""

from __future__ import annotations

from freelance_radar.config import Settings
from freelance_radar.sources.base import SourceAdapter
from freelance_radar.sources.fixture import FixtureSourceAdapter
from freelance_radar.sources.flru import FLruSourceAdapter, FreelanceRuSourceAdapter
from freelance_radar.sources.kwork import KworkSourceAdapter
from freelance_radar.sources.rss import RSSSourceAdapter
from freelance_radar.sources.telegram_channels import TelegramChannelsAdapter


def register_default_adapters(settings: Settings) -> list[SourceAdapter]:
    adapters: list[SourceAdapter] = []

    if settings.source_fixture_enabled:
        adapters.append(FixtureSourceAdapter(settings.fixture_orders_path))

    if settings.source_rss_enabled:
        adapters.append(RSSSourceAdapter(settings.rss_feeds_list()))

    if settings.source_telegram_enabled:
        adapters.append(
            TelegramChannelsAdapter(
                api_id=settings.telegram_api_id,
                api_hash=settings.telegram_api_hash,
                session_path=settings.telegram_session_path,
                channels=settings.telegram_channels_list(),
            )
        )

    if settings.source_kwork_enabled:
        adapters.append(KworkSourceAdapter())

    if settings.source_flru_enabled:
        adapters.append(FLruSourceAdapter())
        adapters.append(FreelanceRuSourceAdapter())

    return adapters


def build_adapters(settings: Settings) -> list[SourceAdapter]:
    return register_default_adapters(settings)
