"""Local fixture source for offline demo and tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from freelance_radar.schemas import RawListing, SourceCapabilities
from freelance_radar.sources.base import SourceAdapter, SourceCollectResult


class FixtureSourceAdapter(SourceAdapter):
    key = "fixture"
    name = "Fixture / demo orders"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    async def probe(self) -> SourceCapabilities:
        exists = self.path.exists()
        return SourceCapabilities(
            can_read=exists,
            can_auto_contact=False,
            contact_channel=None,
            available=exists,
            unavailable_reason=None if exists else f"Fixture file missing: {self.path}",
            notes="Local JSON for pipeline testing. No live network. Auto-contact disabled.",
            alternatives=["Enable RSS or Telegram sources with valid credentials."],
        )

    async def collect(self) -> SourceCollectResult:
        if not self.path.exists():
            return SourceCollectResult(errors=[f"Fixture file not found: {self.path}"])
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return SourceCollectResult(errors=[f"Invalid fixture JSON: {exc}"])

        items = data if isinstance(data, list) else data.get("orders", [])
        listings: list[RawListing] = []
        for item in items:
            listings.append(self._to_listing(item))
        return SourceCollectResult(listings=listings, meta={"count": len(listings)})

    def _to_listing(self, item: dict[str, Any]) -> RawListing:
        published = item.get("published_at")
        published_at = None
        if published:
            published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
        return RawListing(
            external_id=str(item["id"]),
            title=item.get("title"),
            text=item.get("text") or item.get("description") or "",
            url=item.get("url"),
            author_id=item.get("author_id"),
            author_name=item.get("author_name"),
            author_contact=item.get("author_contact"),
            published_at=published_at or datetime.now(timezone.utc),
            extra=item.get("extra") or {},
        )
