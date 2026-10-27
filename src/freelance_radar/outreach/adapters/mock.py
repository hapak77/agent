"""Test/fake outreach adapter — never contacts real people."""

from __future__ import annotations

from freelance_radar.outreach.adapters.base import OutreachAdapter, OutreachResult


class MockOutreachAdapter(OutreachAdapter):
    channel = "mock"

    def __init__(self, *, fail_recipients: set[str] | None = None, flood_wait: bool = False) -> None:
        self.fail_recipients = fail_recipients or set()
        self.flood_wait = flood_wait
        self.sent: list[tuple[str, str]] = []

    async def send(self, *, recipient: str, message: str) -> OutreachResult:
        if self.flood_wait:
            return OutreachResult(
                success=False,
                confirmed=False,
                status="paused",
                error_code="FloodWait",
                error_message="Simulated FloodWait",
                pause_seconds=60,
            )
        if recipient in self.fail_recipients or recipient.startswith("fail:"):
            return OutreachResult(
                success=False,
                confirmed=False,
                status="failed",
                error_code="SEND_ERROR",
                error_message="Simulated send failure",
            )
        self.sent.append((recipient, message))
        return OutreachResult(
            success=True,
            confirmed=True,
            status="sent",
            provider_message_id=f"mock-{len(self.sent)}",
        )
