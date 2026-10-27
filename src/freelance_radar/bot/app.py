"""Aiogram bot factory and notifier."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from freelance_radar.bot.handlers import build_root_router
from freelance_radar.bot.middleware import OwnerOnlyMiddleware
from freelance_radar.config import Settings
from freelance_radar.logging_setup import get_logger

logger = get_logger(__name__)


def create_bot(settings: Settings) -> Bot | None:
    if not settings.telegram_bot_token:
        logger.warning("telegram_bot_token_missing")
        return None
    return Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(settings: Settings) -> Dispatcher:
    dp = Dispatcher()
    dp.message.middleware(OwnerOnlyMiddleware(settings.owner_telegram_id))
    dp.include_router(build_root_router())
    return dp


class OwnerNotifier:
    def __init__(self, bot: Bot | None, owner_id: int) -> None:
        self.bot = bot
        self.owner_id = owner_id

    async def __call__(self, text: str) -> None:
        if not self.bot or not self.owner_id:
            logger.info("notify_stdout", text=text[:500])
            return
        await self.bot.send_message(self.owner_id, text[:4000])
