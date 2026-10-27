"""Kwork adapter — availability probe only for MVP.

Kwork does not provide a documented public API for arbitrary order scraping,
and web pages are protected against unauthorized automation. We do not bypass
CAPTCHA, login walls, or anti-bot protections.
"""

from __future__ import annotations

import httpx

from freelance_radar.schemas import SourceCapabilities
from freelance_radar.sources.base import SourceAdapter, SourceCollectResult


class KworkSourceAdapter(SourceAdapter):
    key = "kwork"
    name = "Kwork"

    async def probe(self) -> SourceCapabilities:
        reachable = False
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.head(
                    "https://kwork.ru",
                    headers={"User-Agent": "FreelanceRadar/0.1 (+availability-check)"},
                )
                reachable = resp.status_code < 500
        except httpx.HTTPError:
            reachable = False

        return SourceCapabilities(
            can_read=False,
            can_auto_contact=False,
            available=False,
            unavailable_reason=(
                "No official public API for project listings; scraping would violate "
                "anti-automation protections. Adapter is a stub until an allowed interface exists."
            ),
            notes=(
                f"Site reachable={reachable}. Official partner/API access required for automation. "
                "Do not enable scraping of protected pages."
            ),
            alternatives=[
                "Manual export / email alerts from Kwork if available",
                "Monitor related public Telegram channels via Telethon",
                "Add public RSS if Kwork or partners publish one",
            ],
        )

    async def collect(self) -> SourceCollectResult:
        caps = await self.probe()
        return SourceCollectResult(
            errors=[caps.unavailable_reason or "Kwork unavailable for automated collection"]
        )
