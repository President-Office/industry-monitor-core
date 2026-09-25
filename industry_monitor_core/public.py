"""Small allowlist helpers for public ETF observation payloads."""

PUBLIC_VALUE_KEYS = {
    "close",
    "change_1d_pct",
    "change_5d_pct",
    "change_20d_pct",
    "excess_5d_pp",
    "excess_20d_pp",
    "volume",
    "amount",
}


def public_observation(item):
    """Return only fields approved for a public observation payload."""
    fields = (
        "id",
        "group",
        "name",
        "code",
        "theme",
        "benchmark",
        "provider",
        "publisher",
        "status",
        "data_date",
        "checked_at",
        "last_success_at",
    )
    result = {key: item[key] for key in fields if key in item}
    result["source_url"] = item["source_url"]
    result["values"] = {
        key: value for key, value in item.get("values", {}).items()
        if key in PUBLIC_VALUE_KEYS
    }
    return result
