"""Priority score calculation."""

from __future__ import annotations

from freelance_radar.db.models import OrderKind
from freelance_radar.schemas import LLMOrderAnalysis, PriorityResult


def compute_priority(analysis: LLMOrderAnalysis) -> PriorityResult:
    """Higher is better. Budget absence does not zero the score."""
    if analysis.order_kind in {
        OrderKind.spam.value,
        OrderKind.advertisement.value,
        OrderKind.free_test.value,
    }:
        return PriorityResult(score=0.0, explanation="Отклонено: спам/реклама/бесплатный тест")

    if analysis.order_kind == OrderKind.vacancy.value:
        return PriorityResult(score=1.5, explanation="Вакансия — низкий приоритет для разовых заказов")

    if analysis.order_kind == OrderKind.discussion.value:
        return PriorityResult(score=1.0, explanation="Обсуждение, не заказ")

    base = 5.0
    base += (analysis.feasibility - 5.0) * 0.6
    base += (5.0 - analysis.risk_score) * 0.4
    base += (5.0 - abs(analysis.complexity - 5.0)) * 0.2

    if not analysis.budget_unknown and analysis.budget_amount is not None:
        # Small budgets still acceptable; slight boost for known budget
        base += 0.8
        if analysis.budget_amount >= 10000:
            base += 1.0
        elif analysis.budget_amount >= 3000:
            base += 0.5
    else:
        base += 0.2  # unknown budget still kept

    if analysis.order_kind == OrderKind.uncertain.value:
        base -= 0.5
        explanation_extra = "неопределённый тип, оставлен"
    elif analysis.order_kind == OrderKind.real_order.value:
        explanation_extra = "реальный заказ"
    else:
        explanation_extra = analysis.order_kind

    if not analysis.is_relevant and analysis.order_kind != OrderKind.uncertain.value:
        base = min(base, 2.0)

    score = max(0.0, min(10.0, round(base, 2)))
    explanation = (
        f"priority={score}: {explanation_extra}; "
        f"feasibility={analysis.feasibility}, complexity={analysis.complexity}, "
        f"risk={analysis.risk_score}, budget="
        f"{'unknown' if analysis.budget_unknown else analysis.budget_amount}"
    )
    return PriorityResult(score=score, explanation=explanation)
