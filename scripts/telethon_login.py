#!/usr/bin/env python3
"""Interactive Telethon login to create a user session file.

Run locally once:
  python scripts/telethon_login.py

Requires TELEGRAM_API_ID and TELEGRAM_API_HASH in .env.
Do not commit the resulting session file.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from freelance_radar.config import get_settings  # noqa: E402


async def main() -> None:
    settings = get_settings()
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        print("Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env")
        sys.exit(1)
    from telethon import TelegramClient

    client = TelegramClient(
        settings.telegram_session_path,
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )
    await client.start()
    me = await client.get_me()
    print(f"Authorized as {me.id} ({me.username})")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
