"""Shared collection and public rendering for reviewed ETF observations."""

import hashlib
import json
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .akshare_etf import (
    AkshareFetchError,
    AkshareUnavailable,
    fetch_history,
    market_observation,
)

STATUS_LABELS = {
    "ok": "已获取",
    "not_published": "尚未见新披露",
    "weekend_closed": "周末休市",
    "stale": "数据已滞后",
    "fetch_failed": "页面暂未更新",
    "pending_review": "暂未纳入观察",
}


def _archive_frame(frame, data, item_id):
    if hasattr(frame, "to_dict"):
        try:
            records = frame.to_dict(orient="records")
        except TypeError:
            records = frame.to_dict("records")
    elif isinstance(frame, list):
        records = frame
    else:
        raise ValueError("AKShare returned an unsupported history shape")
    payload = json.dumps(
        {"adapter": "akshare", "records": records},
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    raw_path = Path(data) / "indicator-archive" / item_id / (
        hashlib.sha256(payload).hexdigest() + ".json"
    )
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if not raw_path.exists():
        raw_path.write_bytes(payload)
    return raw_path.relative_to(data).as_posix()


def _ensure_schema(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS indicator_snapshots (
            id TEXT, run_id TEXT, checked_at TEXT, fetch_status TEXT, payload TEXT,
            PRIMARY KEY (id, run_id)
        )
        """
    )
    db.commit()


def _restore_previous(db, item_id, result):
    previous = db.execute(
        "SELECT payload FROM indicator_snapshots WHERE id=? AND fetch_status='ok' "
        "ORDER BY checked_at DESC, rowid DESC LIMIT 1",
        (item_id,),
    ).fetchone()
    if previous:
        prior = json.loads(previous["payload"])
        result.update({key: prior.get(key) for key in ("data_date", "values")})
        result["last_success_at"] = prior["checked_at"]


def _add_benchmark_comparison(observations):
    benchmark = next((item for item in observations if item.get("benchmark")), None)
    if not benchmark or benchmark["status"] in ("fetch_failed", "pending_review"):
        return
    for item in observations:
        if item.get("group") != "etf" or item.get("benchmark"):
            continue
        if item["status"] in ("fetch_failed", "pending_review"):
            continue
        for periods in (5, 20):
            key = f"change_{periods}d_pct"
            same_window = item.get("_windows", {}).get(str(periods))
            benchmark_window = benchmark.get("_windows", {}).get(str(periods))
            left = item.get("values", {}).get(key)
            right = benchmark.get("values", {}).get(key)
            if same_window and same_window == benchmark_window and left is not None and right is not None:
                item["values"][f"excess_{periods}d_pp"] = str(
                    Decimal(left) - Decimal(right)
                )


def collect_akshare_etfs(
    config,
    data,
    db,
    run_id,
    checked_at,
    fetcher=fetch_history,
    sleep=time.sleep,
    min_interval=2,
):
    """Collect a domain-owned ETF watchlist through the reviewed adapter."""
    _ensure_schema(db)
    adapter = config.get("market_adapters", {}).get("akshare-etf", {})
    if not adapter.get("enabled"):
        return []
    observations = []
    last_request = None
    for item in config["etfs"]:
        result = {
            "id": item["id"],
            "group": "etf",
            "name": item["name"],
            "code": item["code"],
            "theme": item["theme"],
            "benchmark": item["benchmark"],
            "provider": "akshare",
            "source_url": adapter["source_url"],
            "publisher": "Eastmoney via AKShare",
            "checked_at": checked_at,
            "status": "pending_review",
            "data_date": None,
            "values": {},
        }
        fetch_status = "failed"
        try:
            if last_request is not None:
                wait = min_interval - (time.monotonic() - last_request)
                if wait > 0:
                    sleep(wait)
            frame = fetcher(item, checked_at)
            last_request = time.monotonic()
            raw_path = _archive_frame(frame, data, item["id"])
            result.update(market_observation(item, frame, checked_at))
            result.update({
                "id": item["id"],
                "group": "etf",
                "name": item["name"],
                "code": item["code"],
                "theme": item["theme"],
                "benchmark": item["benchmark"],
                "_raw_paths": [raw_path],
            })
            fetch_status = "ok"
        except (
            AkshareFetchError,
            AkshareUnavailable,
            ValueError,
            KeyError,
            TypeError,
            InvalidOperation,
            OSError,
        ) as error:
            _restore_previous(db, item["id"], result)
            result.update({"status": "fetch_failed", "_error": str(error)})
        result["_fetch_status"] = fetch_status
        observations.append(result)
    _add_benchmark_comparison(observations)
    for result in observations:
        db.execute(
            "INSERT OR REPLACE INTO indicator_snapshots VALUES (?,?,?,?,?)",
            (
                result["id"],
                run_id,
                checked_at,
                result["_fetch_status"],
                json.dumps(result, ensure_ascii=False),
            ),
        )
    db.commit()
    return observations
