"""Format order cards for Telegram."""

from __future__ import annotations

from freelance_radar.db.models import Order
from freelance_radar.utils.text import truncate


def format_order_card(order: Order) -> str:
    budget = (
        "неизвестен"
        if order.budget_unknown or order.budget_amount is None
        else f"{order.budget_amount:g} {order.budget_currency or ''}".strip()
    )
    cats = ", ".join(order.categories or []) or "—"
    return (
        f"<b>#{order.id}</b> {truncate(order.llm_summary or order.title or order.raw_text, 120)}\n"
        f"Источник: {order.source.key if order.source else '—'}\n"
        f"Категории: {cats}\n"
        f"Бюджет: {budget}\n"
        f"Сложность: {order.complexity if order.complexity is not None else '—'} | "
        f"Выполнимость: {order.feasibility if order.feasibility is not None else '—'}\n"
        f"Рейтинг: {order.priority_score if order.priority_score is not None else '—'}\n"
        f"{truncate(order.rating_explanation or '', 180)}\n"
        f"Контакт: {order.contact_status.value}\n"
        f"Ссылка: {order.url or '—'}"
    )


def format_stats(stats: dict) -> str:
    return (
        "<b>Статистика</b>\n"
        f"Всего заказов: {stats['orders_total']}\n"
        f"За 24ч: {stats['orders_24h']}\n"
        f"Готовы к контакту: {stats['orders_ready']}\n"
        f"Отправлено (подтверждено): {stats['contacts_sent']}\n"
        f"Ошибок отправки: {stats['contacts_failed']}\n"
        f"Нужен ручной контакт: {stats['manual_contact_required']}"
    )
