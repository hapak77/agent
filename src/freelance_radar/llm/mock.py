"""Deterministic mock LLM for offline tests and dry runs."""

from __future__ import annotations

import re

from freelance_radar.llm.base import LLMClient
from freelance_radar.schemas import LLMOrderAnalysis

_BUDGET_RE = re.compile(
    r"(?:бюджет|budget|оплата|плачу|ставка)?\s*[:=]?\s*(\d[\d\s]{2,8})\s*(₽|руб|rub|usd|\$|€|eur)?",
    re.I,
)

_SPAM_MARKERS = ("заработок без вложений", "подпишись", "крипт сигнал", "хайп", "казино")
_VACANCY_MARKERS = ("вакансия", "штат", "full-time", "полная занятость", "в команду надолго")
_TEST_MARKERS = ("тестовое задание бесплатно", "сделайте тест без оплаты", "free test task")
_AD_MARKERS = ("продаю курс", "наш сервис", "реклама", "промокод")


class MockLLMClient(LLMClient):
    model_name = "mock-v1"

    async def analyze_order(self, *, title: str | None, text: str) -> LLMOrderAnalysis:
        blob = f"{title or ''}\n{text}".lower()

        order_kind = "real_order"
        is_relevant = True
        relevance_reason = "Похоже на запрос услуги"

        wants_work = bool(
            re.search(
                r"(?<![А-Яа-яA-Za-z])(нужен|нужна|нужно|ищу|требуется|заказать|сделать|"
                r"помогите|looking for|need a|need)\b",
                blob,
            )
        )
        # Explicit "not an order" / curiosity-only phrasing
        not_an_order = any(
            p in blob
            for p in (
                "заказ не нужен",
                "заказа нет",
                "просто интересно",
                "не заказ",
            )
        )

        if any(m in blob for m in _SPAM_MARKERS):
            order_kind, is_relevant, relevance_reason = "spam", False, "Признаки спама"
        elif any(m in blob for m in _AD_MARKERS):
            order_kind, is_relevant, relevance_reason = (
                "advertisement",
                False,
                "Рекламное сообщение",
            )
        elif any(m in blob for m in _TEST_MARKERS):
            order_kind, is_relevant, relevance_reason = (
                "free_test",
                False,
                "Бесплатное тестовое",
            )
        elif any(m in blob for m in _VACANCY_MARKERS):
            order_kind, is_relevant, relevance_reason = "vacancy", False, "Вакансия, не разовый заказ"
        elif not_an_order or (
            any(m in blob for m in ("как думаете", "кто знает", "подскажите библиотеку"))
            and not wants_work
        ):
            order_kind, is_relevant, relevance_reason = "discussion", False, "Обсуждение, не заказ"
        elif not wants_work:
            order_kind = "uncertain"
            relevance_reason = "Неясная формулировка, оставляем на ручной просмотр"

        categories: list[str] = []
        mapping = [
            (("python", "скрипт", "api", "telegram-бот", "бот"), "python"),
            (("ии", "нейросет", "rag", "llm", "gpt", "ai"), "ai"),
            (("монтаж", "shorts", "reels", "tiktok", "субтит"), "video"),
            (("лендинг", "сайт", "web", "mvp", "дашборд"), "web"),
            (("парс", "ocr", "pdf", "данн"), "parsing"),
            (("excel", "google sheets", "отчёт", "аналит"), "excel"),
            (("дизайн", "презентац", "инфограф"), "design"),
            (("деплой", "интеграц", "ошибк", "devops"), "devops"),
        ]
        for keys, cat in mapping:
            if any(k in blob for k in keys):
                categories.append(cat)
        if not categories:
            categories = ["other"]

        budget_amount = None
        budget_currency = None
        budget_unknown = True
        match = _BUDGET_RE.search(f"{title or ''}\n{text}")
        if match:
            raw = match.group(1).replace(" ", "")
            try:
                budget_amount = float(raw)
                budget_unknown = False
                cur = (match.group(2) or "RUB").lower()
                if cur in ("$", "usd"):
                    budget_currency = "USD"
                elif cur in ("€", "eur"):
                    budget_currency = "EUR"
                else:
                    budget_currency = "RUB"
            except ValueError:
                pass

        summary = (title or text).strip().split("\n")[0][:120]
        contact_summary = summary[:80]
        complexity = 4.0
        if any(k in blob for k in ("mvp", "интеграц", "нейросет", "rag")):
            complexity = 7.0
        if any(k in blob for k in ("срочн", "asap", "вчера")):
            complexity = min(10.0, complexity + 1.0)

        feasibility = 8.0 if is_relevant else 2.0
        if order_kind == "uncertain":
            feasibility = 5.0
        risk_score = 3.0
        risks: list[str] = []
        if budget_unknown:
            risks.append("бюджет не указан")
        if "бессроч" in blob:
            risks.append("неясные сроки")

        return LLMOrderAnalysis(
            order_kind=order_kind,  # type: ignore[arg-type]
            categories=categories,
            summary=summary,
            budget_amount=budget_amount,
            budget_currency=budget_currency,
            budget_unknown=budget_unknown,
            deadline_text=None,
            requirements=None,
            expected_result=None,
            complexity=complexity,
            feasibility=feasibility,
            risk_score=risk_score,
            risks=risks,
            is_relevant=is_relevant or order_kind == "uncertain",
            relevance_reason=relevance_reason,
            contact_summary=contact_summary,
        )
