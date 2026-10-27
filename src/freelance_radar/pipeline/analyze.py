"""Analyze new orders: prefilter → LLM → score."""

from __future__ import annotations

from freelance_radar.db import repositories as repo
from freelance_radar.db.models import ContactStatus, Order, OrderKind, OrderStatus
from freelance_radar.llm.base import LLMClient
from freelance_radar.logging_setup import get_logger
from freelance_radar.pipeline.prefilter import prefilter_text
from freelance_radar.pipeline.score import compute_priority
from freelance_radar.schemas import LLMOrderAnalysis
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

ACCEPT_KINDS = {OrderKind.real_order, OrderKind.uncertain}
MIN_PRIORITY_FOR_OUTREACH = 3.0


async def analyze_order(session: AsyncSession, order: Order, llm: LLMClient) -> Order:
    order.status = OrderStatus.processing
    await session.flush()

    pre = prefilter_text(order.raw_text, order.title)
    order.passed_prefilter = pre.passed
    order.prefilter_reason = pre.reason

    if not pre.passed:
        order.status = OrderStatus.rejected
        order.order_kind = OrderKind.spam if pre.reason.startswith("hard_block") else OrderKind.discussion
        order.priority_score = 0.0
        order.rating_explanation = f"prefilter: {pre.reason}"
        await session.flush()
        return order

    cached = await repo.find_analysis_cache(session, order.content_hash)
    if cached and cached.order_id != order.id:
        analysis = LLMOrderAnalysis.model_validate(cached.raw_response)
        await repo.save_analysis(
            session,
            order.id,
            model_name=cached.model_name,
            raw_response=cached.raw_response,
            cached=True,
        )
    else:
        analysis = await llm.analyze_order(title=order.title, text=order.raw_text)
        await repo.save_analysis(
            session,
            order.id,
            model_name=llm.model_name,
            raw_response=analysis.model_dump(),
            cached=False,
        )

    _apply_analysis(order, analysis)
    priority = compute_priority(analysis)
    order.priority_score = priority.score
    order.rating_explanation = priority.explanation

    kind = OrderKind(analysis.order_kind)
    if kind in ACCEPT_KINDS and analysis.is_relevant and priority.score >= MIN_PRIORITY_FOR_OUTREACH:
        order.status = OrderStatus.ready_for_outreach
        if not order.author_contact and not order.author_id:
            order.contact_status = ContactStatus.manual_contact_required
            order.contact_message = _build_contact_message(analysis)
        else:
            order.contact_status = ContactStatus.queued
            order.contact_message = _build_contact_message(analysis)
    elif kind == OrderKind.uncertain and priority.score >= 2.0:
        order.status = OrderStatus.analyzed
        order.contact_status = ContactStatus.manual_contact_required
        order.contact_message = _build_contact_message(analysis)
    else:
        order.status = OrderStatus.rejected

    await session.flush()
    logger.info(
        "order_analyzed",
        order_id=order.id,
        kind=order.order_kind.value if order.order_kind else None,
        priority=order.priority_score,
        status=order.status.value,
    )
    return order


def _apply_analysis(order: Order, analysis: LLMOrderAnalysis) -> None:
    order.order_kind = OrderKind(analysis.order_kind)
    order.categories = analysis.categories
    order.llm_summary = analysis.summary
    order.budget_amount = analysis.budget_amount
    order.budget_currency = analysis.budget_currency
    order.budget_unknown = analysis.budget_unknown or analysis.budget_amount is None
    if order.budget_unknown:
        order.budget_amount = None
    order.deadline_text = analysis.deadline_text
    order.requirements = analysis.requirements
    order.expected_result = analysis.expected_result
    order.complexity = analysis.complexity
    order.feasibility = analysis.feasibility
    order.risk_score = analysis.risk_score
    order.risks = analysis.risks


def _build_contact_message(analysis: LLMOrderAnalysis) -> str:
    summary = (analysis.contact_summary or analysis.summary or "ваш проект").strip()
    # Strip trailing punctuation for natural template fill
    summary = summary.rstrip(" .")
    return (
        f"Здравствуйте! Я по поводу вашего заказа: {summary}. "
        "Подскажите, пожалуйста, он ещё актуален?"
    )
