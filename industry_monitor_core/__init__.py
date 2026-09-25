"""Domain-neutral adapters for industry monitoring projects."""

from .akshare_etf import (
    AkshareFetchError,
    AkshareUnavailable,
    fetch_history,
    market_observation,
    normalize_history,
)
from .registry import load_market_registry

__all__ = [
    "AkshareFetchError",
    "AkshareUnavailable",
    "fetch_history",
    "load_market_registry",
    "market_observation",
    "normalize_history",
]
