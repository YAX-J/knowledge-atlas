"""Normalize exact temporal expressions quoted by extraction candidates."""
import re
from datetime import date, datetime, time, timedelta, timezone

from app.schemas.knowledge import FactValidity, TemporalDraft


def _expression_date(expression: str, reference: date | None) -> date | None:
    absolute = re.fullmatch(r"(\d{4})(?:-(\d{2})-(\d{2})|年(\d{1,2})月(\d{1,2})日)", expression)
    if absolute:
        year, month, day, cn_month, cn_day = absolute.groups()
        return date(int(year), int(month or cn_month), int(day or cn_day))
    if reference is None:
        return None
    if expression in {"今天", "今日", "目前", "today"}:
        return reference
    if expression in {"昨天", "昨日", "yesterday"}:
        return reference - timedelta(days=1)
    if expression in {"上周", "本周", "last week", "this week"}:
        days = reference.weekday() + (7 if expression in {"上周", "last week"} else 0)
        return reference - timedelta(days=days)
    if expression in {"上个月", "上月", "本月", "这个月", "last month", "this month"}:
        month = reference.replace(day=1)
        if expression in {"上个月", "上月", "last month"}:
            return (month - timedelta(days=1)).replace(day=1)
        return month
    return None


def proposed_validity(temporal: TemporalDraft, reference: datetime | None) -> FactValidity | None:
    """Represent supported calendar boundaries as UTC at the start of the day."""
    reference_day = reference.astimezone(timezone.utc).date() if reference else None
    try:
        start = _expression_date(temporal.start, reference_day)
        end = _expression_date(temporal.end, reference_day) if temporal.end else None
    except (ValueError, OverflowError):
        return None
    if start is None or (temporal.end and end is None) or (end is not None and end <= start):
        return None
    return FactValidity(
        valid_from=datetime.combine(start, time.min, tzinfo=timezone.utc),
        valid_to=datetime.combine(end, time.min, tzinfo=timezone.utc) if end is not None else None,
    )
