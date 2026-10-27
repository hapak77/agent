"""Collect listings from adapters and persist new orders."""

from __future__ import annotations

from freelance_radar.db import repositories as repo
from freelance_radar.db.models import OrderStatus, SourceStatus
from freelance_radar.logging_setup import get_logger
from freelance_radar.schemas import RawListing
from freelance_radar.sources.base import SourceAdapter
from freelance_radar.utils.text import content_hash, normalize_text, semantic_fingerprint
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


async def ensure_source_registered(
    session: AsyncSession, adapter: SourceAdapter, *, enabled: bool
) -> None:
    caps = await adapter.probe()
    status = SourceStatus.active
    if not caps.available:
        status = SourceStatus.unavailable
    elif not enabled:
        status = SourceStatus.disabled
    await repo.upsert_source(
        session,
        key=adapter.key,
        name=adapter.name,
        adapter=adapter.__class__.__name__,
        enabled=enabled and caps.available,
        status=status,
        config_json=adapter.default_config(),
        capabilities=caps.model_dump(),
    )


async def ingest_adapter(session: AsyncSession, adapter: SourceAdapter) -> dict[str, int]:
    source = await repo.get_source_by_key(session, adapter.key)
    if source is None:
        await ensure_source_registered(session, adapter, enabled=True)
        source = await repo.get_source_by_key(session, adapter.key)
    assert source is not None

    if not source.enabled:
        return {"skipped": 1, "created": 0, "duplicates": 0}

    result = await adapter.collect()
    created = 0
    duplicates = 0

    if result.errors:
        await repo.mark_source_error(session, source, "; ".join(result.errors)[:2000])
        for err in result.errors:
            await repo.log_error(
                session, component="collector", message=err, source_key=adapter.key
            )
    else:
        await repo.mark_source_success(session, source)

    for listing in result.listings:
        outcome = await _persist_listing(session, source.id, listing)
        if outcome == "created":
            created += 1
        else:
            duplicates += 1

    logger.info(
        "ingest_done",
        source=adapter.key,
        created=created,
        duplicates=duplicates,
        errors=len(result.errors),
    )
    return {"created": created, "duplicates": duplicates, "errors": len(result.errors)}


async def _persist_listing(session: AsyncSession, source_id: int, listing: RawListing) -> str:
    existing = await repo.find_order_by_external(session, source_id, listing.external_id)
    if existing:
        return "duplicate"

    normalized = normalize_text(listing.text)
    c_hash = content_hash(listing.text)
    exact = await repo.find_order_by_hash(session, c_hash)
    s_fp = semantic_fingerprint(listing.text)

    is_duplicate = False
    duplicate_group_id = None
    status = OrderStatus.new

    if exact is not None:
        is_duplicate = True
        status = OrderStatus.archived
        group = await repo.get_or_create_duplicate_group(
            session, fingerprint=f"exact:{c_hash}", canonical_order_id=exact.id
        )
        duplicate_group_id = group.id
    else:
        semantic_hits = await repo.find_orders_by_semantic(session, s_fp)
        if semantic_hits:
            is_duplicate = True
            status = OrderStatus.archived
            group = await repo.get_or_create_duplicate_group(
                session,
                fingerprint=f"sem:{s_fp}",
                canonical_order_id=semantic_hits[0].id,
            )
            duplicate_group_id = group.id

    await repo.create_order(
        session,
        source_id=source_id,
        external_id=listing.external_id,
        title=listing.title,
        raw_text=listing.text,
        normalized_text=normalized,
        url=listing.url,
        author_id=listing.author_id,
        author_name=listing.author_name,
        author_contact=listing.author_contact,
        published_at=listing.published_at,
        content_hash=c_hash,
        semantic_fingerprint=s_fp,
        is_duplicate=is_duplicate,
        duplicate_group_id=duplicate_group_id,
        status=status,
        extra_json=listing.extra,
    )
    return "duplicate" if is_duplicate else "created"
