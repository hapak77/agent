"""Data access helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import Select, and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from freelance_radar.db.models import (
    AnalysisResult,
    AppState,
    ContactAttempt,
    ContactStatus,
    DuplicateGroup,
    ErrorLog,
    Order,
    OrderStatus,
    Source,
    SourceStatus,
)


async def upsert_source(
    session: AsyncSession,
    *,
    key: str,
    name: str,
    adapter: str,
    enabled: bool = True,
    status: SourceStatus = SourceStatus.active,
    config_json: dict[str, Any] | None = None,
    capabilities: dict[str, Any] | None = None,
) -> Source:
    result = await session.execute(select(Source).where(Source.key == key))
    source = result.scalar_one_or_none()
    if source is None:
        source = Source(
            key=key,
            name=name,
            adapter=adapter,
            enabled=enabled,
            status=status,
            config_json=config_json or {},
            capabilities=capabilities or {},
        )
        session.add(source)
    else:
        source.name = name
        source.adapter = adapter
        source.enabled = enabled
        source.status = status
        if config_json is not None:
            source.config_json = config_json
        if capabilities is not None:
            source.capabilities = capabilities
    await session.flush()
    return source


async def get_source_by_key(session: AsyncSession, key: str) -> Source | None:
    result = await session.execute(select(Source).where(Source.key == key))
    return result.scalar_one_or_none()


async def list_sources(session: AsyncSession) -> Sequence[Source]:
    result = await session.execute(select(Source).order_by(Source.key))
    return result.scalars().all()


async def mark_source_error(session: AsyncSession, source: Source, message: str) -> None:
    source.status = SourceStatus.error
    source.last_error = message[:2000]
    source.last_error_at = datetime.now(timezone.utc)


async def mark_source_success(session: AsyncSession, source: Source) -> None:
    source.status = SourceStatus.active if source.enabled else SourceStatus.disabled
    source.last_success_at = datetime.now(timezone.utc)
    source.last_error = None


async def find_order_by_external(
    session: AsyncSession, source_id: int, external_id: str
) -> Order | None:
    result = await session.execute(
        select(Order).where(Order.source_id == source_id, Order.external_id == external_id)
    )
    return result.scalar_one_or_none()


async def find_order_by_hash(session: AsyncSession, content_hash: str) -> Order | None:
    result = await session.execute(select(Order).where(Order.content_hash == content_hash).limit(1))
    return result.scalar_one_or_none()


async def find_orders_by_semantic(
    session: AsyncSession, fingerprint: str, limit: int = 20
) -> Sequence[Order]:
    result = await session.execute(
        select(Order)
        .where(Order.semantic_fingerprint == fingerprint, Order.is_duplicate.is_(False))
        .limit(limit)
    )
    return result.scalars().all()


async def create_order(session: AsyncSession, **kwargs: Any) -> Order:
    order = Order(**kwargs)
    session.add(order)
    await session.flush()
    return order


async def get_order(session: AsyncSession, order_id: int) -> Order | None:
    result = await session.execute(
        select(Order)
        .options(selectinload(Order.source), selectinload(Order.contacts))
        .where(Order.id == order_id)
    )
    return result.scalar_one_or_none()


async def list_orders(
    session: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
    status: OrderStatus | None = None,
    contact_status: ContactStatus | None = None,
    min_priority: float | None = None,
) -> Sequence[Order]:
    stmt: Select[tuple[Order]] = (
        select(Order)
        .options(selectinload(Order.source))
        .order_by(Order.priority_score.desc().nullslast(), Order.discovered_at.desc())
        .limit(limit)
        .offset(offset)
    )
    filters = []
    if status is not None:
        filters.append(Order.status == status)
    if contact_status is not None:
        filters.append(Order.contact_status == contact_status)
    if min_priority is not None:
        filters.append(Order.priority_score >= min_priority)
    if filters:
        stmt = stmt.where(and_(*filters))
    result = await session.execute(stmt)
    return result.scalars().all()


async def list_orders_for_pipeline(
    session: AsyncSession, *, statuses: Sequence[OrderStatus], limit: int
) -> Sequence[Order]:
    result = await session.execute(
        select(Order)
        .where(Order.status.in_(list(statuses)))
        .order_by(Order.discovered_at.asc())
        .limit(limit)
    )
    return result.scalars().all()


async def list_outreach_candidates(session: AsyncSession, *, limit: int = 20) -> Sequence[Order]:
    result = await session.execute(
        select(Order)
        .options(selectinload(Order.source), selectinload(Order.contacts))
        .where(
            Order.status == OrderStatus.ready_for_outreach,
            Order.contact_status.in_(
                [ContactStatus.not_contacted, ContactStatus.queued, ContactStatus.manual_contact_required]
            ),
        )
        .order_by(Order.priority_score.desc().nullslast())
        .limit(limit)
    )
    return result.scalars().all()


async def get_or_create_duplicate_group(
    session: AsyncSession, fingerprint: str, canonical_order_id: int | None = None
) -> DuplicateGroup:
    result = await session.execute(
        select(DuplicateGroup).where(DuplicateGroup.fingerprint == fingerprint)
    )
    group = result.scalar_one_or_none()
    if group is None:
        group = DuplicateGroup(fingerprint=fingerprint, canonical_order_id=canonical_order_id)
        session.add(group)
        await session.flush()
    return group


async def save_analysis(
    session: AsyncSession,
    order_id: int,
    *,
    model_name: str,
    raw_response: dict[str, Any],
    cached: bool = False,
    prompt_version: str = "v1",
) -> AnalysisResult:
    result = await session.execute(select(AnalysisResult).where(AnalysisResult.order_id == order_id))
    analysis = result.scalar_one_or_none()
    if analysis is None:
        analysis = AnalysisResult(
            order_id=order_id,
            model_name=model_name,
            raw_response=raw_response,
            cached=cached,
            prompt_version=prompt_version,
        )
        session.add(analysis)
    else:
        analysis.model_name = model_name
        analysis.raw_response = raw_response
        analysis.cached = cached
        analysis.prompt_version = prompt_version
    await session.flush()
    return analysis


async def find_analysis_cache(
    session: AsyncSession, content_hash: str
) -> AnalysisResult | None:
    """Reuse analysis for exact duplicate text from another order."""
    result = await session.execute(
        select(AnalysisResult)
        .join(Order, Order.id == AnalysisResult.order_id)
        .where(Order.content_hash == content_hash)
        .order_by(AnalysisResult.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_contact_attempt(
    session: AsyncSession,
    *,
    order_id: int,
    channel: str,
    recipient: str,
    message_text: str,
    status: ContactStatus,
    confirmed: bool = False,
    error_code: str | None = None,
    error_message: str | None = None,
    provider_message_id: str | None = None,
) -> ContactAttempt:
    attempt = ContactAttempt(
        order_id=order_id,
        channel=channel,
        recipient=recipient,
        message_text=message_text,
        status=status,
        confirmed=confirmed,
        error_code=error_code,
        error_message=error_message,
        provider_message_id=provider_message_id,
    )
    session.add(attempt)
    await session.flush()
    return attempt


async def has_successful_contact(
    session: AsyncSession, order_id: int, recipient: str | None = None
) -> bool:
    filters = [
        ContactAttempt.order_id == order_id,
        ContactAttempt.status == ContactStatus.sent,
        ContactAttempt.confirmed.is_(True),
    ]
    if recipient:
        filters.append(ContactAttempt.recipient == recipient)
    result = await session.execute(select(ContactAttempt.id).where(and_(*filters)).limit(1))
    return result.scalar_one_or_none() is not None


async def count_contacts_since(
    session: AsyncSession, *, since: datetime, statuses: Sequence[ContactStatus] | None = None
) -> int:
    stmt = select(func.count(ContactAttempt.id)).where(ContactAttempt.attempted_at >= since)
    if statuses:
        stmt = stmt.where(ContactAttempt.status.in_(list(statuses)))
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def last_contact_at(session: AsyncSession) -> datetime | None:
    result = await session.execute(
        select(func.max(ContactAttempt.attempted_at)).where(
            ContactAttempt.status == ContactStatus.sent,
            ContactAttempt.confirmed.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def log_error(
    session: AsyncSession,
    *,
    component: str,
    message: str,
    source_key: str | None = None,
    details: dict[str, Any] | None = None,
) -> ErrorLog:
    entry = ErrorLog(
        component=component,
        source_key=source_key,
        message=message[:4000],
        details=details or {},
    )
    session.add(entry)
    await session.flush()
    return entry


async def list_recent_errors(session: AsyncSession, limit: int = 20) -> Sequence[ErrorLog]:
    result = await session.execute(
        select(ErrorLog).order_by(ErrorLog.created_at.desc()).limit(limit)
    )
    return result.scalars().all()


async def get_app_flag(session: AsyncSession, key: str, default: Any = None) -> Any:
    result = await session.execute(select(AppState).where(AppState.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        return default
    return row.value_json.get("value", default)


async def set_app_flag(session: AsyncSession, key: str, value: Any) -> AppState:
    result = await session.execute(select(AppState).where(AppState.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        row = AppState(key=key, value_json={"value": value})
        session.add(row)
    else:
        row.value_json = {"value": value}
    await session.flush()
    return row


async def get_stats(session: AsyncSession) -> dict[str, Any]:
    orders_total = await session.scalar(select(func.count(Order.id))) or 0
    orders_ready = await session.scalar(
        select(func.count(Order.id)).where(Order.status == OrderStatus.ready_for_outreach)
    ) or 0
    contacts_sent = await session.scalar(
        select(func.count(ContactAttempt.id)).where(
            ContactAttempt.status == ContactStatus.sent,
            ContactAttempt.confirmed.is_(True),
        )
    ) or 0
    contacts_failed = await session.scalar(
        select(func.count(ContactAttempt.id)).where(ContactAttempt.status == ContactStatus.failed)
    ) or 0
    manual = await session.scalar(
        select(func.count(Order.id)).where(
            Order.contact_status == ContactStatus.manual_contact_required
        )
    ) or 0
    day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    orders_24h = await session.scalar(
        select(func.count(Order.id)).where(Order.discovered_at >= day_ago)
    ) or 0
    return {
        "orders_total": orders_total,
        "orders_ready": orders_ready,
        "orders_24h": orders_24h,
        "contacts_sent": contacts_sent,
        "contacts_failed": contacts_failed,
        "manual_contact_required": manual,
    }


async def list_outreach_history(session: AsyncSession, limit: int = 20) -> Sequence[ContactAttempt]:
    result = await session.execute(
        select(ContactAttempt)
        .options(selectinload(ContactAttempt.order))
        .order_by(ContactAttempt.attempted_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def update_order_fields(session: AsyncSession, order_id: int, **fields: Any) -> None:
    await session.execute(update(Order).where(Order.id == order_id).values(**fields))
