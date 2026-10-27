from aiogram import Router

from freelance_radar.bot.handlers.commands import router as commands_router


def build_root_router() -> Router:
    root = Router()
    root.include_router(commands_router)
    return root
