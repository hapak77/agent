"""Bot formatter unit tests."""

from freelance_radar.bot.formatters import format_order_card, format_stats
from freelance_radar.db.models import ContactStatus, Order, OrderStatus, Source


def test_format_order_card_unknown_budget():
    source = Source(id=1, key="fixture", name="Fixture", adapter="Fixture")
    order = Order(
        id=1,
        source_id=1,
        external_id="x",
        raw_text="test order text long enough",
        normalized_text="test",
        content_hash="abc",
        budget_unknown=True,
        budget_amount=None,
        categories=["python"],
        complexity=4,
        feasibility=8,
        priority_score=6.5,
        rating_explanation="priority=6.5",
        contact_status=ContactStatus.manual_contact_required,
        status=OrderStatus.ready_for_outreach,
        llm_summary="Скрипт API",
        url="https://example.com/1",
    )
    order.source = source
    text = format_order_card(order)
    assert "неизвестен" in text
    assert "https://example.com/1" in text


def test_format_stats():
    text = format_stats(
        {
            "orders_total": 10,
            "orders_24h": 2,
            "orders_ready": 3,
            "contacts_sent": 1,
            "contacts_failed": 0,
            "manual_contact_required": 2,
        }
    )
    assert "10" in text
