"""Shared Pydantic schemas for pipeline and LLM outputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class RawListing(BaseModel):
    """Normalized raw item collected from a source adapter."""

    external_id: str
    title: str | None = None
    text: str
    url: str | None = None
    author_id: str | None = None
    author_name: str | None = None
    author_contact: str | None = None
    published_at: datetime | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class SourceCapabilities(BaseModel):
    can_read: bool = False
    can_auto_contact: bool = False
    contact_channel: str | None = None
    requires_user_session: bool = False
    notes: str = ""
    available: bool = True
    unavailable_reason: str | None = None
    alternatives: list[str] = Field(default_factory=list)


class LLMOrderAnalysis(BaseModel):
    """Structured LLM response for order analysis."""

    order_kind: Literal[
        "real_order",
        "discussion",
        "advertisement",
        "spam",
        "free_test",
        "vacancy",
        "uncertain",
    ] = "uncertain"
    categories: list[str] = Field(default_factory=list)
    summary: str = ""
    budget_amount: float | None = None
    budget_currency: str | None = None
    budget_unknown: bool = True
    deadline_text: str | None = None
    requirements: str | None = None
    expected_result: str | None = None
    complexity: float = Field(ge=0, le=10, default=5.0)
    feasibility: float = Field(ge=0, le=10, default=5.0)
    risk_score: float = Field(ge=0, le=10, default=5.0)
    risks: list[str] = Field(default_factory=list)
    is_relevant: bool = True
    relevance_reason: str = ""
    contact_summary: str = ""

    @field_validator("complexity", "feasibility", "risk_score", mode="before")
    @classmethod
    def _clamp_scores(cls, value: object) -> object:
        if value is None:
            return 5.0
        try:
            num = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 5.0
        return max(0.0, min(10.0, num))

    @field_validator("budget_amount", mode="before")
    @classmethod
    def _budget_none(cls, value: object) -> object:
        if value in ("", "null", "None", "unknown", "неизвестно"):
            return None
        return value


class PriorityResult(BaseModel):
    score: float
    explanation: str


class OutreachDecision(BaseModel):
    action: Literal["send", "manual", "skip", "pause"]
    reason: str
    recipient: str | None = None
    channel: str | None = None
    message: str | None = None
