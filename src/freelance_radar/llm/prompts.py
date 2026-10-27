"""Compact prompts for order analysis."""

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """Ты аналитик фриланс-заказов. Отвечай ТОЛЬКО валидным JSON без markdown.
Классифицируй объявление: real_order | discussion | advertisement | spam | free_test | vacancy | uncertain.
Не отбрасывай полезные заказы только из-за отсутствия бюджета или ключевых слов.
Не выдумывай бюджет: если суммы нет — budget_unknown=true и budget_amount=null.
Кратко суммируй суть для первого сообщения (contact_summary, до 12 слов).
Оцени complexity, feasibility, risk_score от 0 до 10.
Категории из списка или близкие: python, bots, ai, video, design, web, parsing, data, excel, devops, other.
"""


def build_user_prompt(*, title: str | None, text: str) -> str:
    title_part = (title or "").strip()
    body = (text or "").strip()
    # Keep prompt compact to reduce cost
    if len(body) > 2500:
        body = body[:2500] + "…"
    return (
        f"Заголовок: {title_part or '(нет)'}\n"
        f"Текст:\n{body}\n\n"
        "Верни JSON со полями: order_kind, categories, summary, budget_amount, "
        "budget_currency, budget_unknown, deadline_text, requirements, expected_result, "
        "complexity, feasibility, risk_score, risks, is_relevant, relevance_reason, "
        "contact_summary."
    )
