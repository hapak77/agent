#!/usr/bin/env python3
"""Run a single collect+analyze cycle (no bot)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from freelance_radar.app_factory import build_pipeline  # noqa: E402
from freelance_radar.config import get_settings  # noqa: E402
from freelance_radar.db.session import dispose_db, init_db  # noqa: E402
from freelance_radar.logging_setup import setup_logging  # noqa: E402


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    await init_db(settings)
    pipeline = build_pipeline(settings)
    await pipeline.register_sources()
    result = await pipeline.run_once()
    print(result)
    await dispose_db()


if __name__ == "__main__":
    asyncio.run(main())
