"""Outreach orchestration with rate limits and dedupe."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from freelance_radar.config import Settings
from freelance_radar.db import repositories as repo
from freelance_radar.db.models import ContactStatus, Order, OrderStatus
from freelance_radar.db.session import session_scope
from freelance_radar.logging_setup import get_logger
from freelance_radar.outreach.adapters.base import OutreachAdapter, OutreachResult
from freelance_radar.schemas import OutreachDecision

logger = get_logger(__name__)

NotifyCallback = Callable[[str], Awaitable[None]]


class OutreachService:
    def __init__(
        self,
        *,
        settings: Settings,
        adapters: dict[str, OutreachAdapter],
        notify: NotifyCallback | None = None,
    ) -> None:
        self.settings = settings
        self.adapters = adapters
        self.notify = notify
        self._paused_until: datetime | None = None

    async def process_queue(self, *, limit: int = 10) -> list[dict]:
        results: list[dict] = []
        if not await self._outreach_globally_allowed():
            return results

        async with session_scope() as session:
            candidates = await repo.list_outreach_candidates(session, limit=limit)
            for order in candidates:
                decision = await self._decide(session, order)
                outcome = await self._execute(session, order, decision)
                results.append(outcome)
                if outcome.get("pause"):
                    break
        return results

    async def _outreach_globally_allowed(self) -> bool:
        if self._paused_until and datetime.now(timezone.utc) < self._paused_until:
            logger.info("outreach_paused_until", until=self._paused_until.isoformat())
            return False
        async with session_scope() as session:
            if await repo.get_app_flag(session, "outreach_stopped", False):
                return False
            if await repo.get_app_flag(session, "pipeline_paused", False):
                return False
        if not self.settings.outreach_enabled and not self.settings.outreach_dry_run:
            # Even with dry_run we may simulate; if both off, skip
            return False
        return True

    async def _decide(self, session: AsyncSession, order: Order) -> OutreachDecision:
        message = order.contact_message or (
            "Здравствуйте! Я по поводу вашего заказа. "
            "Подскажите, пожалуйста, он ещё актуален?"
        )

        if order.order_kind and order.order_kind.value not in {"real_order", "uncertain"}:
            return OutreachDecision(action="skip", reason="not_a_real_order")

        recipient = order.author_contact or order.author_id
        if not recipient:
            return OutreachDecision(
                action="manual",
                reason="author_unknown",
                message=message,
            )

        if await repo.has_successful_contact(session, order.id, recipient):
            return OutreachDecision(action="skip", reason="already_contacted", recipient=recipient)

        # Rate limits
        now = datetime.now(timezone.utc)
        hour_count = await repo.count_contacts_since(
            session,
            since=now - timedelta(hours=1),
            statuses=[ContactStatus.sent],
        )
        day_count = await repo.count_contacts_since(
            session,
            since=now - timedelta(days=1),
            statuses=[ContactStatus.sent],
        )
        if hour_count >= self.settings.outreach_max_per_hour:
            return OutreachDecision(action="pause", reason="hourly_limit")
        if day_count >= self.settings.outreach_max_per_day:
            return OutreachDecision(action="pause", reason="daily_limit")

        last = await repo.last_contact_at(session)
        if last is not None:
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if (now - last).total_seconds() < self.settings.outreach_min_interval_seconds:
                return OutreachDecision(action="pause", reason="min_interval")

        # Prefer telegram adapter if recipient looks like tg id
        channel = "telegram" if self._looks_telegram(recipient) else "mock"
        if channel not in self.adapters:
            if "mock" in self.adapters and (
                self.settings.outreach_dry_run or self.settings.app_env == "test"
            ):
                channel = "mock"
            else:
                return OutreachDecision(
                    action="manual",
                    reason="no_allowed_channel",
                    recipient=recipient,
                    message=message,
                )

        if not self.settings.outreach_enabled:
            # Prepare manual / dry-run path
            if self.settings.outreach_dry_run and channel in self.adapters:
                return OutreachDecision(
                    action="send",
                    reason="dry_run_or_disabled_flag",
                    recipient=recipient,
                    channel=channel,
                    message=message,
                )
            return OutreachDecision(
                action="manual",
                reason="outreach_disabled",
                recipient=recipient,
                message=message,
            )

        return OutreachDecision(
            action="send",
            reason="ok",
            recipient=recipient,
            channel=channel,
            message=message,
        )

    async def _execute(
        self, session: AsyncSession, order: Order, decision: OutreachDecision
    ) -> dict:
        if decision.action == "skip":
            order.contact_status = ContactStatus.skipped
            await session.flush()
            return {"order_id": order.id, "action": "skip", "reason": decision.reason}

        if decision.action == "pause":
            return {"order_id": order.id, "action": "pause", "reason": decision.reason, "pause": True}

        if decision.action == "manual":
            order.contact_status = ContactStatus.manual_contact_required
            order.contact_message = decision.message
            await session.flush()
            text = self._manual_notify_text(order, decision.message or "")
            await self._notify(text)
            return {
                "order_id": order.id,
                "action": "manual",
                "reason": decision.reason,
                "message": decision.message,
                "url": order.url,
            }

        assert decision.action == "send"
        assert decision.channel and decision.recipient and decision.message
        adapter = self.adapters[decision.channel]

        # Force dry-run adapter behavior if configured
        result = await adapter.send(recipient=decision.recipient, message=decision.message)

        if result.status == "paused":
            await self._record_attempt(
                session, order, decision, result, status=ContactStatus.paused
            )
            if result.pause_seconds:
                self._paused_until = datetime.now(timezone.utc) + timedelta(
                    seconds=result.pause_seconds
                )
                await repo.set_app_flag(session, "outreach_stopped", True)
            await self._notify(
                f"⏸ Outreach paused: {result.error_code} — {result.error_message}\n"
                f"Order #{order.id}"
            )
            return {"order_id": order.id, "action": "pause", "result": result.status, "pause": True}

        if result.status == "skipped" or (
            result.error_code == "DRY_RUN"
        ):
            order.contact_status = ContactStatus.manual_contact_required
            await self._record_attempt(
                session, order, decision, result, status=ContactStatus.manual_contact_required
            )
            await self._notify(self._manual_notify_text(order, decision.message))
            return {
                "order_id": order.id,
                "action": "manual",
                "reason": result.error_code or "dry_run",
                "url": order.url,
            }

        if result.success and result.confirmed:
            await self._record_attempt(
                session, order, decision, result, status=ContactStatus.sent
            )
            order.contact_status = ContactStatus.sent
            order.status = OrderStatus.contacted
            await self._notify(
                f"✅ Контакт отправлен (подтверждено)\n"
                f"Заказ #{order.id}: {order.llm_summary or order.title or ''}\n"
                f"Канал: {decision.channel}\n"
                f"Текст: {decision.message}"
            )
            return {"order_id": order.id, "action": "sent", "confirmed": True}

        # Failure or unconfirmed — never claim success
        await self._record_attempt(
            session, order, decision, result, status=ContactStatus.failed
        )
        order.contact_status = ContactStatus.failed
        await self._notify(
            f"❌ Отправка не удалась / не подтверждена\n"
            f"Заказ #{order.id}\n"
            f"Ошибка: {result.error_code} {result.error_message or ''}\n"
            f"Ссылка: {order.url or '—'}\n"
            f"Черновик:\n{decision.message}"
        )
        return {
            "order_id": order.id,
            "action": "failed",
            "confirmed": False,
            "error": result.error_message,
        }

    async def _record_attempt(
        self,
        session: AsyncSession,
        order: Order,
        decision: OutreachDecision,
        result: OutreachResult,
        *,
        status: ContactStatus,
    ) -> None:
        # Unique constraint may block repeats — catch by checking first
        existing = await repo.has_successful_contact(
            session, order.id, decision.recipient or ""
        )
        if existing and status == ContactStatus.sent:
            return
        await repo.create_contact_attempt(
            session,
            order_id=order.id,
            channel=decision.channel or "unknown",
            recipient=decision.recipient or "unknown",
            message_text=decision.message or "",
            status=status,
            confirmed=bool(result.confirmed and status == ContactStatus.sent),
            error_code=result.error_code,
            error_message=result.error_message,
            provider_message_id=result.provider_message_id,
        )

    def _manual_notify_text(self, order: Order, message: str) -> str:
        return (
            f"✍️ Требуется ручной контакт\n"
            f"Заказ #{order.id}: {order.llm_summary or order.title or ''}\n"
            f"Ссылка: {order.url or '—'}\n"
            f"Причина: автор неизвестен или автоотправка недоступна\n"
            f"Текст:\n{message}"
        )

    async def _notify(self, text: str) -> None:
        if self.notify:
            try:
                await self.notify(text)
            except Exception:  # noqa: BLE001
                logger.exception("notify_failed")

    @staticmethod
    def _looks_telegram(recipient: str) -> bool:
        r = recipient.strip()
        return r.isdigit() or r.startswith("tg://user?id=")
