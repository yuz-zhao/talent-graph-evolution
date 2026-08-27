"""Strict source-time parsing. Missing publication dates are never fabricated."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

UTC = timezone.utc


def parse_datetime(value) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
    normalized = re.sub(r"\s+", " ", normalized)
    candidates = [normalized, normalized.replace("Z", "+00:00")]
    for candidate in candidates:
        try:
            stamp = datetime.fromisoformat(candidate)
            return stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp.astimezone(UTC)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y%m%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(normalized, fmt).replace(tzinfo=UTC)
        except ValueError:
            pass
    try:
        stamp = parsedate_to_datetime(text)
        return stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp.astimezone(UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def normalize_source_time(value, observed_at=None) -> dict:
    raw = str(value or "").strip()
    observed = parse_datetime(observed_at) or datetime.now(UTC)
    result = {
        "publish_time_raw": raw,
        "source_published_at": "",
        "time_precision": "unknown",
        "time_source": "unknown",
        "time_parse_confidence": 0.0,
    }
    if not raw:
        return result

    relative = re.search(r"(\d+)\s*(?:天|日)前", raw)
    if raw in {"今天", "今日", "刚刚"}:
        stamp = observed
        result.update(time_precision="day", time_source="relative_text", time_parse_confidence=0.75)
    elif raw == "昨天":
        stamp = observed - timedelta(days=1)
        result.update(time_precision="day", time_source="relative_text", time_parse_confidence=0.8)
    elif relative:
        stamp = observed - timedelta(days=int(relative.group(1)))
        result.update(time_precision="day", time_source="relative_text", time_parse_confidence=0.8)
    elif re.search(r"20\d{2}.*(?:春招|秋招|校招|招聘)", raw):
        result.update(time_precision="campaign", time_source="campaign_period", time_parse_confidence=0.6)
        return result
    else:
        stamp = parse_datetime(raw)
        if not stamp:
            return result
        precision = "day" if re.search(r"\d{1,2}[^\d]+\d{1,2}", raw) or re.fullmatch(r"\d{8}", raw) else "month"
        result.update(time_precision=precision, time_source="source_field", time_parse_confidence=0.95 if precision == "day" else 0.85)

    if stamp > observed + timedelta(days=2) or stamp.year < 2000:
        result.update(time_source="invalid", time_parse_confidence=0.0)
        return result
    result["source_published_at"] = stamp.replace(microsecond=0).isoformat()
    return result
