from __future__ import annotations

import re
from datetime import datetime, timedelta


TIME_FMT = "%Y-%m-%d %H:%M"


def now_str() -> str:
    return datetime.now().strftime(TIME_FMT)


def parse_relative_time(text: str | None) -> str | None:
    if not text:
        return None

    content = text.strip()
    if not content:
        return None

    try:
        return datetime.strptime(content, TIME_FMT).strftime(TIME_FMT)
    except ValueError:
        pass

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
