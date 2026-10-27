"""Scheduled collect / analyze / outreach jobs."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from freelance_radar.config import Settings
from freelance_radar.logging_setup import get_logger
from freelance_radar.outreach.service import OutreachService
from freelance_radar.pipeline.runner import PipelineRunner

logger = get_logger(__name__)


def build_scheduler(
    *,
    settings: Settings,
    pipeline: PipelineRunner,
    outreach: OutreachService,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)

    async def collect_and_analyze() -> None:
        try:
            result = await pipeline.run_once()
            logger.info("scheduled_pipeline", **result)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001
            logger.exception("scheduled_pipeline_failed")

    async def outreach_tick() -> None:
        try:
            outcomes = await outreach.process_queue(limit=5)
            if outcomes:
                logger.info("scheduled_outreach", count=len(outcomes))
        except Exception:  # noqa: BLE001
            logger.exception("scheduled_outreach_failed")

    scheduler.add_job(
        collect_and_analyze,
        "interval",
        seconds=settings.collect_interval_seconds,
        id="collect_analyze",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        outreach_tick,
        "interval",
        seconds=settings.outreach_interval_seconds,
        id="outreach",
        replace_existing=True,
        max_instances=1,
    )
    return scheduler
