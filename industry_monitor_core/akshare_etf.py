"""Shared AKShare ETF market-data adapter.

The adapter only normalizes a reviewed public daily-history shape. Domain
projects decide which instruments to observe and how to present them.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from zoneinfo import ZoneInfo


LOCAL_TZ = ZoneInfo("Asia/Shanghai")


class AkshareUnavailable(RuntimeError):
    """Raised when the optional AKShare dependency is not installed."""


class AkshareFetchError(RuntimeError):
    """Raised when AKShare cannot return a usable upstream response."""


def _records(frame):
    if hasattr(frame, "to_dict"):
        try:
            return frame.to_dict(orient="records")
        except TypeError:
            return frame.to_dict("records")
    if isinstance(frame, list):
        return frame
    raise ValueError("AKShare returned an unsupported history shape")


def _value(row, *names):
    for name in names:
        if name in row:
            return row[name]
    return None


def _code(value):
    if value is None:
        return None
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text.zfill(6) if text.isdigit() else text


def _day(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise ValueError("Invalid AKShare disclosure date")


def _number(value, low=None, high=None):
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        raise ValueError("Invalid AKShare numeric value") from None
    if not parsed.is_finite() or (low is not None and parsed < low) or (
        high is not None and parsed > high
    ):
        raise ValueError("AKShare numeric value outside reviewed range")
    return parsed


def normalize_history(frame, code, today):
    """Normalize ``fund_etf_hist_em`` rows without trusting row order."""
    rows = _records(frame)
    if len(rows) > 250:
        raise ValueError("AKShare history response is unexpectedly large")
    points = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("AKShare history row is not an object")
        row_code = _value(row, "代码", "基金代码", "symbol")
        if row_code is not None and _code(row_code) != code:
            raise ValueError("AKShare response contains another ETF")
        current = _day(_value(row, "日期", "date"))
        if current > today:
            raise ValueError("Future AKShare disclosure date")
        close = _number(_value(row, "收盘", "close"), Decimal("0"), Decimal("1000000"))
        change = _number(_value(row, "涨跌幅", "change_pct"), Decimal("-100"), Decimal("1000"))
        volume = _number(_value(row, "成交量", "volume"), Decimal("0"), Decimal("1e18"))
        amount = _number(_value(row, "成交额", "amount"), Decimal("0"), Decimal("1e18"))
        if close is None:
            raise ValueError("Missing AKShare ETF close")
        point = {
            "date": current.isoformat(),
            "close": str(close),
            "change_pct": None if change is None else str(change),
            "volume": None if volume is None else str(volume),
            "amount": None if amount is None else str(amount),
        }
        previous = points.get(point["date"])
        if previous is not None and previous != point:
            raise ValueError("Conflicting AKShare values for one date")
        points[point["date"]] = point
    return sorted(points.values(), key=lambda item: item["date"], reverse=True)


def market_observation(item, frame, checked_at):
    """Build a bounded public-safe ETF market snapshot."""
    today = datetime.fromisoformat(checked_at).astimezone(LOCAL_TZ).date()
    points = normalize_history(frame, item["code"], today)
    result = {
        "provider": "akshare",
        "source_url": "https://quote.eastmoney.com/",
        "publisher": "Eastmoney via AKShare",
        "checked_at": checked_at,
        "status": "not_published",
        "data_date": None,
        "values": {},
    }
    if not points:
        return result
    latest = points[0]
    age = (today - date.fromisoformat(latest["date"])).days
    result.update({
        "data_date": latest["date"],
        "status": (
            "stale" if age > 7 else
            "weekend_closed" if today.weekday() >= 5 else
            "ok" if age == 0 else
            "not_published"
        ),
        "values": {
            "close": latest["close"],
            "change_1d_pct": latest["change_pct"],
            "volume": latest["volume"],
            "amount": latest["amount"],
        },
        "_windows": {},
    })
    for periods in (5, 20):
        if len(points) > periods:
            current = Decimal(points[0]["close"])
            previous = Decimal(points[periods]["close"])
            if previous != 0:
                result["values"][f"change_{periods}d_pct"] = str(
                    ((current / previous - 1) * 100).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                )
                result["_windows"][str(periods)] = [
                    point["date"] for point in points[:periods + 1]
                ]
    return result


def fetch_history(item, checked_at, ak_module=None):
    """Fetch one ETF history through AKShare."""
    if ak_module is None:
        try:
            import akshare as ak_module
        except ImportError as error:
            raise AkshareUnavailable(
                "Install the reviewed AKShare dependency to enable this adapter"
            ) from error
    today = datetime.fromisoformat(checked_at).astimezone(LOCAL_TZ).date()
    start = (today - timedelta(days=70)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    try:
        return ak_module.fund_etf_hist_em(
            symbol=item["code"], period="daily", start_date=start, end_date=end, adjust=""
        )
    except Exception as error:
        raise AkshareFetchError("AKShare history request failed") from error
