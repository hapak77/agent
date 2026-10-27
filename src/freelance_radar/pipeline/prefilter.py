"""Cheap rule-based prefilter before LLM calls."""

from __future__ import annotations

from dataclasses import dataclass

IRRELEVANT_HARD = (
    "крипт сигнал",
    "сигналы в тг",
    "казино",
    "ставки на спорт",
    "18+",
    "onlyfans",
    "наркот",
)

SOFT_POSITIVE = (
    "нужен",
    "ищу",
    "требуется",
    "заказать",
    "сделать",
    "помогите",
    "нужно",
    "looking for",
    "need a",
    "freelancer",
    "фриланс",
    "бюджет",
    "срочно",
    "разработать",
    "настроить",
    "исправить",
    "монтаж",
    "лендинг",
    "бот",
    "парс",
    "excel",
    "презентац",
)


@dataclass
class PrefilterResult:
    passed: bool
    reason: str


def prefilter_text(text: str, title: str | None = None) -> PrefilterResult:
    blob = f"{title or ''}\n{text}".lower()
    if len(blob.strip()) < 20:
        return PrefilterResult(False, "too_short")
    for marker in IRRELEVANT_HARD:
        if marker in blob:
            return PrefilterResult(False, f"hard_block:{marker}")
    # Keep uncertain items — do not require keywords
    if any(m in blob for m in SOFT_POSITIVE):
        return PrefilterResult(True, "keyword_hit")
    return PrefilterResult(True, "uncertain_keep")
