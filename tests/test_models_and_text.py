"""Unit tests for text utils and scoring."""

from freelance_radar.pipeline.prefilter import prefilter_text
from freelance_radar.pipeline.score import compute_priority
from freelance_radar.schemas import LLMOrderAnalysis
from freelance_radar.utils.text import content_hash, normalize_text, semantic_fingerprint


def test_normalize_and_hash_stable():
    a = content_hash("  Hello   World  ")
    b = content_hash("hello world")
    assert a == b
    assert normalize_text("А\u00a0Б") == "а б"


def test_semantic_fingerprint_similar():
    f1 = semantic_fingerprint("Нужен Python скрипт для API и Google Sheets")
    f2 = semantic_fingerprint("Нужен python скрипт для api и google sheets!!!")
    assert f1 == f2


def test_prefilter_blocks_spam_keeps_uncertain():
    blocked = prefilter_text("Крипт сигнал и казино каждый день подпишись")
    assert blocked.passed is False
    kept = prefilter_text("Может кто-нибудь помочь с небольшой автоматизацией документов?")
    assert kept.passed is True


def test_priority_unknown_budget_not_zero():
    analysis = LLMOrderAnalysis(
        order_kind="real_order",
        categories=["python"],
        summary="скрипт",
        budget_unknown=True,
        budget_amount=None,
        complexity=4,
        feasibility=8,
        risk_score=3,
        is_relevant=True,
        contact_summary="скрипт API",
    )
    result = compute_priority(analysis)
    assert result.score >= 3.0


def test_priority_small_budget_kept():
    analysis = LLMOrderAnalysis(
        order_kind="real_order",
        categories=["video"],
        summary="shorts",
        budget_unknown=False,
        budget_amount=1500,
        complexity=3,
        feasibility=8,
        risk_score=2,
        is_relevant=True,
        contact_summary="монтаж shorts",
    )
    result = compute_priority(analysis)
    assert result.score >= 3.0


def test_priority_spam_zero():
    analysis = LLMOrderAnalysis(order_kind="spam", is_relevant=False)
    assert compute_priority(analysis).score == 0.0
