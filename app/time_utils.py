from __future__ import annotations

import re
from datetime import datetime, timedelta


TIME_FMT = "%Y-%m-%d %H:%M:%S"
LEGACY_TIME_FMTS = (
    TIME_FMT,
    "%Y-%m-%d %H:%M",
)


def now_str() -> str:
    return datetime.now().strftime(TIME_FMT)


def normalize_db_time(text: str | None) -> str | None:
    if not text:
        return None

    content = text.strip()
    if not content:
        return None

    for fmt in LEGACY_TIME_FMTS:
        try:
            return datetime.strptime(content, fmt).strftime(TIME_FMT)
        except ValueError:
            pass

    chinese_match = re.fullmatch(
        r"(\d{4})年(\d{1,2})月(\d{1,2})日(?:\s*)?(\d{1,2})[点时:：](\d{1,2})分?(?:(\d{1,2})秒?)?",
        content,
    )
    if chinese_match:
        year, month, day, hour, minute, second = chinese_match.groups()
        try:
            parsed = datetime(
                int(year),
                int(month),
                int(day),
                int(hour),
                int(minute),
                int(second or 0),
            )
            return parsed.strftime(TIME_FMT)
        except ValueError:
            return None

    chinese_date_match = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日", content)
    if chinese_date_match:
        year, month, day = chinese_date_match.groups()
        try:
            parsed = datetime(int(year), int(month), int(day), 0, 0, 0)
            return parsed.strftime(TIME_FMT)
        except ValueError:
            return None

    iso_candidate = content.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso_candidate)
        if parsed.tzinfo is not None:
            # 写库前统一转成本地无时区时间，避免落库 TZ 串。
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed.strftime(TIME_FMT)
    except ValueError:
        return None


def parse_db_datetime(text: str | None) -> datetime | None:
    normalized = normalize_db_time(text)
    if not normalized:
        return None
    return datetime.strptime(normalized, TIME_FMT)


def parse_relative_time(text: str | None) -> str | None:
    if not text:
        return None

    content = text.strip()
    if not content:
        return None

    normalized = normalize_db_time(content)
    if normalized:
        return normalized

    base = datetime.now()

    patterns = [
        (r"(\d+)\s*分钟[前之]?前?", timedelta(minutes=-1)),
        (r"(\d+)\s*小时[前之]?前?", timedelta(hours=-1)),
        (r"(\d+)\s*天[前之]?前?", timedelta(days=-1)),
        (r"(\d+)\s*分钟后", timedelta(minutes=1)),
        (r"(\d+)\s*小时后", timedelta(hours=1)),
        (r"(\d+)\s*天后", timedelta(days=1)),
    ]
    for pattern, unit in patterns:
        match = re.fullmatch(pattern, content)
        if match:
            count = int(match.group(1))
            delta = unit * count
            return (base + delta).strftime(TIME_FMT)

    if content in {"现在", "刚刚", "此刻"}:
        return base.strftime(TIME_FMT)
    if content == "昨天":
        return (base - timedelta(days=1)).strftime(TIME_FMT)
    if content == "今天":
        return base.strftime(TIME_FMT)
    if content == "明天":
        return (base + timedelta(days=1)).strftime(TIME_FMT)

    return None
