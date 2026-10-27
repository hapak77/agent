"""FL.ru / Freelance.ru adapters — availability probe stubs.

These platforms typically require authenticated sessions and block unauthorized
automation. We only probe public reachability and report limitations.
"""

from __future__ import annotations

import httpx

from freelance_radar.schemas import SourceCapabilities
from freelance_radar.sources.base import SourceAdapter, SourceCollectResult


class FLruSourceAdapter(SourceAdapter):
    key = "flru"
    name = "FL.ru"

    async def probe(self) -> SourceCapabilities:
        reachable = False
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.head(
                    "https://www.fl.ru",
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
                "FL.ru projects require authenticated access; no approved public scrape API. "
                "Automated collection is disabled to respect ToS and anti-bot protections."
            ),
            notes=f"Site reachable={reachable}. Enable only with official/allowed API credentials.",
            alternatives=[
                "Use FL.ru RSS/email digests if your account provides them (paste URL into RSS_FEED_URLS)",
                "Forward order notifications to a private Telegram channel you control",
                "Fixture/RSS sources for pipeline validation",
            ],
        )

    async def collect(self) -> SourceCollectResult:
        caps = await self.probe()
        return SourceCollectResult(
            errors=[caps.unavailable_reason or "FL.ru unavailable for automated collection"]
        )


class FreelanceRuSourceAdapter(SourceAdapter):
    key = "freelance_ru"
    name = "Freelance.ru"

    async def probe(self) -> SourceCapabilities:
        reachable = False
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.head(
                    "https://freelance.ru",
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
                "Freelance.ru has no documented public orders API for third-party bots; "
                "protected pages are not scraped."
            ),
            notes=f"Site reachable={reachable}.",
            alternatives=[
                "Subscribe to public RSS if offered and add to RSS_FEED_URLS",
                "Telegram communities that repost projects",
            ],
        )

    async def collect(self) -> SourceCollectResult:
        caps = await self.probe()
        return SourceCollectResult(
            errors=[caps.unavailable_reason or "Freelance.ru unavailable for automated collection"]
        )
