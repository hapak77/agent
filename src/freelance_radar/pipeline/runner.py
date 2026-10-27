"""End-to-end pipeline orchestration."""

from __future__ import annotations

from freelance_radar.config import Settings
from freelance_radar.db import repositories as repo
from freelance_radar.db.models import OrderStatus
from freelance_radar.db.session import session_scope
from freelance_radar.llm.base import LLMClient
from freelance_radar.logging_setup import get_logger
from freelance_radar.pipeline.analyze import analyze_order
from freelance_radar.pipeline.ingest import ensure_source_registered, ingest_adapter
from freelance_radar.sources.base import SourceAdapter

logger = get_logger(__name__)


class PipelineRunner:
    def __init__(
        self,
        *,
        settings: Settings,
        adapters: list[SourceAdapter],
        llm: LLMClient,
    ) -> None:
        self.settings = settings
        self.adapters = adapters
        self.llm = llm

    async def register_sources(self) -> None:
        async with session_scope() as session:
            enabled_map = {
                "fixture": self.settings.source_fixture_enabled,
                "rss": self.settings.source_rss_enabled,
                "telegram": self.settings.source_telegram_enabled,
                "kwork": self.settings.source_kwork_enabled,
                "flru": self.settings.source_flru_enabled,
                "freelance_ru": self.settings.source_flru_enabled,
            }
            for adapter in self.adapters:
                await ensure_source_registered(
                    session, adapter, enabled=enabled_map.get(adapter.key, True)
                )

    async def collect_all(self) -> dict[str, dict[str, int]]:
        paused = await self._is_paused()
        if paused:
            logger.info("collect_skipped_paused")
            return {}
        summary: dict[str, dict[str, int]] = {}
        for adapter in self.adapters:
            async with session_scope() as session:
                summary[adapter.key] = await ingest_adapter(session, adapter)
        return summary

    async def process_new(self) -> int:
        paused = await self._is_paused()
        if paused:
            return 0
        processed = 0
        async with session_scope() as session:
            orders = await repo.list_orders_for_pipeline(
                session,
                statuses=[OrderStatus.new],
                limit=self.settings.pipeline_batch_size,
            )
            for order in orders:
                try:
                    await analyze_order(session, order, self.llm)
                    processed += 1
                except Exception as exc:  # noqa: BLE001
                    await repo.log_error(
                        session,
                        component="pipeline",
                        message=f"analyze failed for order {order.id}: {exc}",
                    )
                    order.status = OrderStatus.rejected
                    logger.exception("analyze_failed", order_id=order.id)
        return processed

    async def run_once(self) -> dict[str, object]:
        collected = await self.collect_all()
        processed = await self.process_new()
        return {"collected": collected, "processed": processed}

    async def _is_paused(self) -> bool:
        async with session_scope() as session:
            return bool(await repo.get_app_flag(session, "pipeline_paused", False))
