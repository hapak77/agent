from freelance_radar.outreach.adapters.base import OutreachAdapter, OutreachResult
from freelance_radar.outreach.adapters.mock import MockOutreachAdapter
from freelance_radar.outreach.adapters.telegram_dm import TelegramDMAdapter

__all__ = [
    "OutreachAdapter",
    "OutreachResult",
    "MockOutreachAdapter",
    "TelegramDMAdapter",
]
