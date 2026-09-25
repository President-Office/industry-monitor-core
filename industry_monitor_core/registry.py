"""Validation for domain-owned daily market observation registries."""

import json
import re
from pathlib import Path
from urllib.parse import urlsplit


def load_market_registry(path, expected_domain):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise ValueError("Unsupported market observation registry")
    if config.get("domain") != expected_domain:
        raise ValueError("Market observation registry belongs to another domain")
    adapters = config.get("market_adapters")
    if not isinstance(adapters, dict):
        raise ValueError("Market observation registry needs market_adapters")
    adapter = adapters.get("akshare-etf")
    if not isinstance(adapter, dict):
        raise ValueError("AKShare ETF adapter is missing")
    if not isinstance(adapter.get("enabled"), bool):
        raise ValueError("AKShare ETF adapter needs an explicit enabled flag")
    if adapter["enabled"]:
        if adapter.get("review_status") not in ("sample_only", "production"):
            raise ValueError("Enabled market adapter needs an explicit review")
        for field in ("package", "function", "source_url"):
            if not isinstance(adapter.get(field), str) or not adapter[field]:
                raise ValueError("Enabled market adapter is missing its contract")
    etfs = config.get("etfs")
    if not isinstance(etfs, list) or not 1 <= len(etfs) <= 6:
        raise ValueError("ETF watchlist must contain between 1 and 6 items")
    ids = set()
    codes = set()
    benchmarks = 0
    for item in etfs:
        if not isinstance(item, dict):
            raise ValueError("ETF watchlist item must be an object")
        if not re.fullmatch(r"[a-z0-9-]+", str(item.get("id", ""))) or item["id"] in ids:
            raise ValueError("Invalid or duplicate ETF ID")
        if not re.fullmatch(r"\d{6}", str(item.get("code", ""))) or item["code"] in codes:
            raise ValueError("Invalid or duplicate ETF code")
        if not isinstance(item.get("name"), str) or not item["name"].strip():
            raise ValueError("ETF name is required")
        if not isinstance(item.get("theme"), str) or not item["theme"].strip():
            raise ValueError("ETF theme is required")
        if not isinstance(item.get("benchmark"), bool):
            raise ValueError("ETF benchmark flag must be boolean")
        if item["benchmark"]:
            benchmarks += 1
        if item.get("url"):
            parsed = urlsplit(item["url"])
            if parsed.scheme != "https" or not parsed.hostname:
                raise ValueError("ETF reference URL must use HTTPS")
        ids.add(item["id"])
        codes.add(item["code"])
    if benchmarks != 1:
        raise ValueError("Exactly one ETF benchmark is required")
    return config
