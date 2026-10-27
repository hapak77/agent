"""Outreach channel adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class OutreachResult:
    success: bool
    confirmed: bool
    status: str  # sent | failed | paused | skipped
    error_code: str | None = None
    error_message: str | None = None
    provider_message_id: str | None = None
    pause_seconds: int | None = None


class OutreachAdapter(ABC):
    channel: str

    @abstractmethod
    async def send(self, *, recipient: str, message: str) -> OutreachResult:
        raise NotImplementedError

    async def close(self) -> None:
        return None
