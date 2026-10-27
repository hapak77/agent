"""RSS/Atom feed source adapter (public feeds only)."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

from freelance_radar.logging_setup import get_logger
from freelance_radar.schemas import RawListing, SourceCapabilities
from freelance_radar.sources.base import SourceAdapter, SourceCollectResult

logger = get_logger(__name__)


class RSSSourceAdapter(SourceAdapter):
    key = "rss"
    name = "RSS / Atom public feeds"

    def __init__(self, feed_urls: list[str], timeout: float = 20.0) -> None:
        self.feed_urls = feed_urls
        self.timeout = timeout

    async def probe(self) -> SourceCapabilities:
        if not self.feed_urls:
            return SourceCapabilities(
                can_read=False,
                can_auto_contact=False,
                available=False,
                unavailable_reason="No RSS_FEED_URLS configured",
                notes=(
                    "Reads only publicly accessible RSS/Atom feeds you provide. "
                    "Does not bypass login walls or CAPTCHA."
                ),
                alternatives=[
                    "Add public freelance board RSS URLs to RSS_FEED_URLS",
                    "Use fixture source for offline demo",
                    "Use Telegram channels you already have access to",
                ],
            )
        ok = 0
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for url in self.feed_urls[:3]:
                try:
                    resp = await client.get(url, headers={"User-Agent": "FreelanceRadar/0.1"})
                    if resp.status_code == 200 and resp.text:
                        ok += 1
                except httpx.HTTPError:
                    continue
        available = ok > 0
        return SourceCapabilities(
            can_read=available,
            can_auto_contact=False,
            available=available,
            unavailable_reason=None if available else "Configured feeds unreachable",
            notes="Public RSS only. Auto-contact not available via RSS.",
            alternatives=["manual_contact_required for all RSS orders"],
        )

    async def collect(self) -> SourceCollectResult:
        if not self.feed_urls:
            return SourceCollectResult(errors=["No RSS feed URLs configured"])

        listings: list[RawListing] = []
        errors: list[str] = []
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for url in self.feed_urls:
                try:
                    resp = await client.get(url, headers={"User-Agent": "FreelanceRadar/0.1"})
                    if resp.status_code == 429:
                        errors.append(f"HTTP 429 for {url}; backing off")
                        continue
                    if resp.status_code >= 400:
                        errors.append(f"HTTP {resp.status_code} for {url}")
                        continue
                    parsed = feedparser.parse(resp.text)
                    for entry in parsed.entries:
                        listing = self._entry_to_listing(entry, feed_url=url)
                        if listing:
                            listings.append(listing)
                except httpx.HTTPError as exc:
                    errors.append(f"{url}: {exc}")
                    logger.warning("rss_collect_failed", url=url, error=str(exc))
        return SourceCollectResult(
            listings=listings, errors=errors, meta={"feeds": len(self.feed_urls)}
        )

    def _entry_to_listing(self, entry: Any, *, feed_url: str) -> RawListing | None:
        entry_id = getattr(entry, "id", None) or getattr(entry, "link", None)
        title = getattr(entry, "title", None) or ""
        summary = getattr(entry, "summary", None) or getattr(entry, "description", None) or ""
        link = getattr(entry, "link", None)
        if not entry_id:
            return None
        text = f"{title}\n{summary}".strip()
        if not text:
            return None
        published_at = None
        published = getattr(entry, "published", None) or getattr(entry, "updated", None)
        if published:
            try:
                published_at = parsedate_to_datetime(published)
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError, IndexError):
                published_at = datetime.now(timezone.utc)
        author = getattr(entry, "author", None)
        return RawListing(
            external_id=str(entry_id)[:255],
            title=title[:512] or None,
            text=text,
            url=link or feed_url,
            author_name=author,
            published_at=published_at,
            extra={"feed_url": feed_url},
        )
