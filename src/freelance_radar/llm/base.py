"""Abstract LLM client."""

from __future__ import annotations

from abc import ABC, abstractmethod

from freelance_radar.schemas import LLMOrderAnalysis


class LLMClient(ABC):
    model_name: str = "unknown"

    @abstractmethod
    async def analyze_order(self, *, title: str | None, text: str) -> LLMOrderAnalysis:
        raise NotImplementedError
