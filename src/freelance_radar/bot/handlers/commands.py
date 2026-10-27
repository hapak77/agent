"""Control bot commands."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from freelance_radar.bot.formatters import format_order_card, format_stats
from freelance_radar.db import repositories as repo
from freelance_radar.db.session import session_scope

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Freelance Radar AI\n\n"
        "Команды:\n"
        "/orders — найденные заказы\n"
        "/outreach — история контактов\n"
        "/sources — источники и ошибки\n"
        "/settings — флаги\n"
        "/stats — статистика\n"
        "/pause — пауза пайплайна\n"
        "/resume — снять паузу\n"
        "/stop_outreach — остановить автоконтакт\n"
        "/start_outreach — разрешить автоконтакт (нужен OUTREACH_ENABLED)"
    )


@router.message(Command("orders"))
async def cmd_orders(message: Message) -> None:
    async with session_scope() as session:
        orders = await repo.list_orders(session, limit=10)
    if not orders:
        await message.answer("Заказов пока нет.")
        return
    chunks = [format_order_card(o) for o in orders]
    # Telegram message limit ~4096
    buf = ""
    for chunk in chunks:
        if len(buf) + len(chunk) + 2 > 4000:
            await message.answer(buf, parse_mode="HTML")
            buf = chunk
        else:
            buf = f"{buf}\n\n{chunk}" if buf else chunk
    if buf:
        await message.answer(buf, parse_mode="HTML")


@router.message(Command("outreach"))
async def cmd_outreach(message: Message) -> None:
    async with session_scope() as session:
        attempts = await repo.list_outreach_history(session, limit=15)
    if not attempts:
        await message.answer("История контактов пуста.")
        return
    lines = []
    for a in attempts:
        conf = "confirmed" if a.confirmed else "not_confirmed"
        lines.append(
            f"#{a.id} order={a.order_id} {a.status.value} ({conf})\n"
            f"{a.channel} → {a.recipient}\n"
            f"{(a.message_text or '')[:200]}\n"
            f"err={a.error_code or '—'}"
        )
    await message.answer("\n\n".join(lines)[:4000])


@router.message(Command("sources"))
async def cmd_sources(message: Message) -> None:
    async with session_scope() as session:
        sources = await repo.list_sources(session)
        errors = await repo.list_recent_errors(session, limit=8)
    if not sources:
        await message.answer("Источники ещё не зарегистрированы.")
        return
    lines = []
    for s in sources:
        caps = s.capabilities or {}
        lines.append(
            f"• <b>{s.key}</b> ({s.name})\n"
            f"  enabled={s.enabled} status={s.status.value}\n"
            f"  can_read={caps.get('can_read')} auto_contact={caps.get('can_auto_contact')}\n"
            f"  note={caps.get('unavailable_reason') or caps.get('notes') or '—'}\n"
            f"  last_error={s.last_error or '—'}"
        )
    text = "\n".join(lines)
    if errors:
        text += "\n\nПоследние ошибки:\n"
        text += "\n".join(f"- [{e.component}] {e.message[:200]}" for e in errors)
    await message.answer(text[:4000], parse_mode="HTML")


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    async with session_scope() as session:
        paused = await repo.get_app_flag(session, "pipeline_paused", False)
        outreach_stopped = await repo.get_app_flag(session, "outreach_stopped", False)
    await message.answer(
        f"pipeline_paused={paused}\n"
        f"outreach_stopped={outreach_stopped}\n"
        "Флаги окружения (OUTREACH_ENABLED, DRY_RUN и т.д.) задаются в .env."
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    async with session_scope() as session:
        stats = await repo.get_stats(session)
    await message.answer(format_stats(stats), parse_mode="HTML")


@router.message(Command("pause"))
async def cmd_pause(message: Message) -> None:
    async with session_scope() as session:
        await repo.set_app_flag(session, "pipeline_paused", True)
    await message.answer("Пайплайн поставлен на паузу.")


@router.message(Command("resume"))
async def cmd_resume(message: Message) -> None:
    async with session_scope() as session:
        await repo.set_app_flag(session, "pipeline_paused", False)
    await message.answer("Пайплайн возобновлён.")


@router.message(Command("stop_outreach"))
async def cmd_stop_outreach(message: Message) -> None:
    async with session_scope() as session:
        await repo.set_app_flag(session, "outreach_stopped", True)
    await message.answer("Автоконтакт остановлен.")


@router.message(Command("start_outreach"))
async def cmd_start_outreach(message: Message) -> None:
    async with session_scope() as session:
        await repo.set_app_flag(session, "outreach_stopped", False)
    await message.answer(
        "Флаг outreach_stopped снят. "
        "Реальная отправка возможна только при OUTREACH_ENABLED=true и "
        "OUTREACH_DRY_RUN=false, а также настроенном канале."
    )
