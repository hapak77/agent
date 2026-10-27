"""Mock LLM classification cases."""

import pytest

from freelance_radar.llm.mock import MockLLMClient


@pytest.mark.asyncio
async def test_mock_detects_budget_and_categories():
    llm = MockLLMClient()
    result = await llm.analyze_order(
        title="API",
        text="Нужен Python бот и API. Бюджет 5000 руб.",
    )
    assert result.order_kind == "real_order"
    assert result.budget_unknown is False
    assert result.budget_amount == 5000
    assert "python" in result.categories


@pytest.mark.asyncio
async def test_mock_unknown_budget():
    llm = MockLLMClient()
    result = await llm.analyze_order(
        title=None,
        text="Нужен RAG ассистент для бизнеса, бюджет пока не определили.",
    )
    assert result.budget_unknown is True
    assert result.budget_amount is None
    assert result.is_relevant is True


@pytest.mark.asyncio
async def test_mock_irrelevant_discussion():
    llm = MockLLMClient()
    result = await llm.analyze_order(
        title="вопрос",
        text="Ребят, как думаете, какая библиотека лучше? Просто интересно.",
    )
    assert result.order_kind == "discussion"
    assert result.is_relevant is False


@pytest.mark.asyncio
async def test_mock_vacancy():
    llm = MockLLMClient()
    result = await llm.analyze_order(
        title="работа",
        text="Вакансия: ищем разработчика в штат на полную занятость в команду надолго.",
    )
    assert result.order_kind == "vacancy"
