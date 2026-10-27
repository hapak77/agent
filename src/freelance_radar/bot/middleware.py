"""Owner-only access middleware."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject


class OwnerOnlyMiddleware(BaseMiddleware):
    def __init__(self, owner_id: int) -> None:
        self.owner_id = owner_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            user = event.from_user
            if not user or (self.owner_id and user.id != self.owner_id):
                if event.text and event.text.startswith("/"):
                    await event.answer("Доступ запрещён.")
                return None
            if not self.owner_id:
                await event.answer(
                    "OWNER_TELEGRAM_ID не задан. Укажите свой Telegram ID в .env."
                )
                return None
        return await handler(event, data)
