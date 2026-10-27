"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite+aiosqlite:///./data/freelance_radar.db"
    timezone: str = "Europe/Moscow"

    telegram_bot_token: str = ""
    owner_telegram_id: int = 0

    telegram_api_id: int | None = None
    telegram_api_hash: str = ""
    telegram_session_path: str = "./data/telethon.session"
    telegram_source_channels: str = ""

    llm_provider: str = "openai_compatible"
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 2
    llm_use_mock: bool = False

    collect_interval_seconds: int = 300
    outreach_interval_seconds: int = 60
    pipeline_batch_size: int = 50

    outreach_enabled: bool = False
    outreach_min_interval_seconds: int = 30
    outreach_max_per_hour: int = 10
    outreach_max_per_day: int = 40
    outreach_dry_run: bool = True

    source_fixture_enabled: bool = True
    source_rss_enabled: bool = True
    source_telegram_enabled: bool = False
    source_kwork_enabled: bool = False
    source_flru_enabled: bool = False

    rss_feed_urls: str = ""
    fixture_orders_path: str = "./data/fixture_orders.json"

    default_contact_template: str = Field(
        default=(
            "Здравствуйте! Я по поводу вашего заказа: {order_summary}. "
            "Подскажите, пожалуйста, он ещё актуален?"
        )
    )

    @field_validator("owner_telegram_id", mode="before")
    @classmethod
    def _empty_owner_id(cls, value: object) -> object:
        if value == "" or value is None:
            return 0
        return value

    @field_validator("telegram_api_id", mode="before")
    @classmethod
    def _empty_api_id(cls, value: object) -> object:
        if value == "" or value is None:
            return None
        return value

    def telegram_channels_list(self) -> list[str]:
        if not self.telegram_source_channels.strip():
            return []
        return [c.strip() for c in self.telegram_source_channels.split(",") if c.strip()]

    def rss_feeds_list(self) -> list[str]:
        if not self.rss_feed_urls.strip():
            return []
        return [u.strip() for u in self.rss_feed_urls.split(",") if u.strip()]

    @property
    def sync_database_url(self) -> str:
        """URL suitable for Alembic (sync driver)."""
        url = self.database_url
        if url.startswith("sqlite+aiosqlite://"):
            return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
        if url.startswith("postgresql+psycopg://"):
            return url
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
