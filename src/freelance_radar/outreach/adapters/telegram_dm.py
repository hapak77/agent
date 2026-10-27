"""Telegram DM outreach via Telethon user session.

Only sends when OUTREACH is enabled and recipient user id is known.
Respects FloodWait — does not bypass Telegram limits.
"""

from __future__ import annotations

from freelance_radar.logging_setup import get_logger
from freelance_radar.outreach.adapters.base import OutreachAdapter, OutreachResult

logger = get_logger(__name__)


class TelegramDMAdapter(OutreachAdapter):
    channel = "telegram"

    def __init__(
        self,
        *,
        api_id: int | None,
        api_hash: str,
        session_path: str,
        dry_run: bool = True,
    ) -> None:
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_path = session_path
        self.dry_run = dry_run
        self._client = None

    async def send(self, *, recipient: str, message: str) -> OutreachResult:
        if self.dry_run:
            return OutreachResult(
                success=False,
                confirmed=False,
                status="skipped",
                error_code="DRY_RUN",
                error_message="OUTREACH_DRY_RUN=true — message not sent",
            )
        if not self.api_id or not self.api_hash:
            return OutreachResult(
                success=False,
                confirmed=False,
                status="failed",
                error_code="NO_CREDENTIALS",
                error_message="Telethon credentials missing",
            )

        user_id = self._parse_user_id(recipient)
        if user_id is None:
            return OutreachResult(
                success=False,
                confirmed=False,
                status="failed",
                error_code="BAD_RECIPIENT",
                error_message=f"Cannot resolve recipient: {recipient}",
            )

        try:
            from telethon import TelegramClient
            from telethon.errors import FloodWaitError, UserPrivacyRestrictedError, PeerFloodError
        except ImportError as exc:
            return OutreachResult(
                success=False,
                confirmed=False,
                status="failed",
                error_code="IMPORT",
                error_message=str(exc),
            )

        client = TelegramClient(self.session_path, int(self.api_id), self.api_hash)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                return OutreachResult(
                    success=False,
                    confirmed=False,
                    status="failed",
                    error_code="UNAUTHORIZED",
                    error_message="Telethon session not authorized",
                )
            sent = await client.send_message(user_id, message)
            msg_id = str(getattr(sent, "id", "")) or None
            # Only confirm if Telethon returned a message object with id
            if msg_id:
                return OutreachResult(
                    success=True,
                    confirmed=True,
                    status="sent",
                    provider_message_id=msg_id,
                )
            return OutreachResult(
                success=False,
                confirmed=False,
                status="failed",
                error_code="UNCONFIRMED",
                error_message="Send returned no message id — not reporting as success",
            )
        except FloodWaitError as exc:
            logger.warning("outreach_floodwait", seconds=exc.seconds)
            return OutreachResult(
                success=False,
                confirmed=False,
                status="paused",
                error_code="FloodWait",
                error_message=f"FloodWait {exc.seconds}s",
                pause_seconds=int(exc.seconds),
            )
        except (UserPrivacyRestrictedError, PeerFloodError) as exc:
            return OutreachResult(
                success=False,
                confirmed=False,
                status="failed",
                error_code=type(exc).__name__,
                error_message=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("outreach_send_failed")
            return OutreachResult(
                success=False,
                confirmed=False,
                status="failed",
                error_code="EXCEPTION",
                error_message=str(exc),
            )
        finally:
            await client.disconnect()

    @staticmethod
    def _parse_user_id(recipient: str) -> int | None:
        recipient = recipient.strip()
        if recipient.startswith("tg://user?id="):
            recipient = recipient.split("=", 1)[1]
        if recipient.isdigit():
            return int(recipient)
        return None
