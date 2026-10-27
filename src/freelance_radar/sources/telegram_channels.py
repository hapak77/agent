"""Telegram channels/groups reader via Telethon user session.

Important limitations:
- A Telegram *bot* cannot read arbitrary chats; user session (Telethon) is required.
- Only channels/groups the account can already access are readable.
- Auto-contact is only possible via private messages when rules and FloodWait allow it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from freelance_radar.logging_setup import get_logger
from freelance_radar.schemas import RawListing, SourceCapabilities
from freelance_radar.sources.base import SourceAdapter, SourceCollectResult

logger = get_logger(__name__)


class TelegramChannelsAdapter(SourceAdapter):
    key = "telegram"
    name = "Telegram channels/groups (Telethon)"

    def __init__(
        self,
        *,
        api_id: int | None,
        api_hash: str,
        session_path: str,
        channels: list[str],
        limit_per_channel: int = 30,
    ) -> None:
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_path = session_path
        self.channels = channels
        self.limit_per_channel = limit_per_channel

    def _credentials_ok(self) -> bool:
        return bool(self.api_id and self.api_hash and self.channels)

    async def probe(self) -> SourceCapabilities:
        if not self._credentials_ok():
            return SourceCapabilities(
                can_read=False,
                can_auto_contact=False,
                requires_user_session=True,
                available=False,
                unavailable_reason=(
                    "TELEGRAM_API_ID / TELEGRAM_API_HASH / TELEGRAM_SOURCE_CHANNELS not configured"
                ),
                notes=(
                    "Telegram bots cannot scrape arbitrary chats. "
                    "This adapter needs a Telethon user session and channels you already joined. "
                    "Do not bypass bans, CAPTCHA, or private invite restrictions."
                ),
                alternatives=[
                    "Configure Telethon credentials and a pre-authorized session file",
                    "Use public RSS feeds of communities that publish orders",
                    "Use fixture source for pipeline testing",
                ],
            )

        session_file = Path(self.session_path)
        if not session_file.exists() and not session_file.with_suffix(".session").exists():
            # Telethon may create session without extension depending on path
            pass

        try:
            from telethon import TelegramClient  # noqa: F401
        except ImportError:
            return SourceCapabilities(
                can_read=False,
                can_auto_contact=False,
                available=False,
                unavailable_reason="telethon package not installed",
                alternatives=["pip install telethon"],
            )

        # Soft probe: do not force interactive login in automated environments
        session_exists = (
            session_file.exists()
            or Path(f"{self.session_path}.session").exists()
            or Path(str(session_file) + ".session").exists()
        )
        if not session_exists:
            return SourceCapabilities(
                can_read=False,
                can_auto_contact=False,
                requires_user_session=True,
                available=False,
                unavailable_reason=(
                    f"Telethon session not found at {self.session_path}. "
                    "Run scripts/telethon_login.py interactively once."
                ),
                notes="After login, reading joined public channels becomes possible.",
                alternatives=["Create session via scripts/telethon_login.py"],
            )

        return SourceCapabilities(
            can_read=True,
            can_auto_contact=True,
            contact_channel="telegram",
            requires_user_session=True,
            available=True,
            notes=(
                "Can read configured channels accessible to the user session. "
                "Outbound DMs must respect FloodWait and platform rules; "
                "outreach is gated by OUTREACH_ENABLED and rate limits."
            ),
        )

    async def collect(self) -> SourceCollectResult:
        caps = await self.probe()
        if not caps.available or not caps.can_read:
            return SourceCollectResult(
                errors=[caps.unavailable_reason or "Telegram source unavailable"]
            )

        try:
            from telethon import TelegramClient
            from telethon.errors import FloodWaitError, ChannelPrivateError, UsernameInvalidError
        except ImportError as exc:
            return SourceCollectResult(errors=[str(exc)])

        listings: list[RawListing] = []
        errors: list[str] = []

        client = TelegramClient(self.session_path, int(self.api_id or 0), self.api_hash)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                return SourceCollectResult(
                    errors=[
                        "Telethon session is not authorized. "
                        "Run scripts/telethon_login.py interactively."
                    ]
                )
            for channel in self.channels:
                try:
                    entity = await client.get_entity(channel)
                    async for message in client.iter_messages(entity, limit=self.limit_per_channel):
                        if not message or not message.message:
                            continue
                        author_id = None
                        author_name = None
                        if message.sender_id:
                            author_id = str(message.sender_id)
                        try:
                            sender = await message.get_sender()
                            if sender:
                                author_name = getattr(sender, "username", None) or getattr(
                                    sender, "first_name", None
                                )
                        except Exception:
                            pass
                        published = message.date
                        if published and published.tzinfo is None:
                            published = published.replace(tzinfo=timezone.utc)
                        username = getattr(entity, "username", None)
                        url = (
                            f"https://t.me/{username}/{message.id}"
                            if username
                            else f"tg://private?channel={channel}&msg={message.id}"
                        )
                        listings.append(
                            RawListing(
                                external_id=f"{channel}:{message.id}",
                                title=None,
                                text=message.message,
                                url=url,
                                author_id=author_id,
                                author_name=author_name,
                                author_contact=f"tg://user?id={author_id}" if author_id else None,
                                published_at=published or datetime.now(timezone.utc),
                                extra={"channel": channel, "message_id": message.id},
                            )
                        )
                except FloodWaitError as exc:
                    errors.append(f"FloodWait {exc.seconds}s for {channel}; pausing")
                    logger.warning("telegram_floodwait", channel=channel, seconds=exc.seconds)
                    break
                except (ChannelPrivateError, UsernameInvalidError, ValueError) as exc:
                    errors.append(f"{channel}: {exc}")
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{channel}: {exc}")
                    logger.warning("telegram_collect_error", channel=channel, error=str(exc))
        finally:
            await client.disconnect()

        return SourceCollectResult(
            listings=listings, errors=errors, meta={"channels": len(self.channels)}
        )
