"""Application entrypoint."""

from __future__ import annotations

import asyncio
import signal

from freelance_radar.app_factory import build_notifier, build_outreach, build_pipeline
from freelance_radar.bot.app import create_bot, create_dispatcher
from freelance_radar.config import get_settings
from freelance_radar.db.session import dispose_db, init_db
from freelance_radar.logging_setup import get_logger, setup_logging
from freelance_radar.scheduler.jobs import build_scheduler

logger = get_logger(__name__)


async def run() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("starting", env=settings.app_env)

    await init_db(settings)

    pipeline = build_pipeline(settings)
    await pipeline.register_sources()

    notifier = build_notifier(settings)
    outreach = build_outreach(settings, notifier)

    # Initial pass
    result = await pipeline.run_once()
    logger.info("initial_pipeline", result=result)

    scheduler = build_scheduler(settings=settings, pipeline=pipeline, outreach=outreach)
    scheduler.start()

    bot = create_bot(settings)
    dp = create_dispatcher(settings)

    stop_event = asyncio.Event()

    def _stop(*_: object) -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    polling_task = None
    if bot:
        polling_task = asyncio.create_task(dp.start_polling(bot))
        logger.info("bot_polling_started")
    else:
        logger.warning("bot_disabled_no_token")

    await stop_event.wait()
    logger.info("shutting_down")
    scheduler.shutdown(wait=False)
    if polling_task:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
    if bot:
        await bot.session.close()
    await dispose_db()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
