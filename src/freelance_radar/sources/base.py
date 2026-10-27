"""Base source adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from freelance_radar.schemas import RawListing, SourceCapabilities


@dataclass
class SourceCollectResult:
    listings: list[RawListing] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


class SourceAdapter(ABC):
    key: str
    name: str

    @abstractmethod
    async def probe(self) -> SourceCapabilities:
        """Check real availability and automation rules without collecting."""

    @abstractmethod
    async def collect(self) -> SourceCollectResult:
        """Collect new listings via allowed interfaces only."""

    def default_config(self) -> dict[str, Any]:
        return {}
