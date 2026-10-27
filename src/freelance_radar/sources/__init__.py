"""Source adapters registry."""

from freelance_radar.sources.base import SourceAdapter, SourceCollectResult
from freelance_radar.sources.registry import build_adapters, register_default_adapters

__all__ = [
    "SourceAdapter",
    "SourceCollectResult",
    "build_adapters",
    "register_default_adapters",
]
