"""Resolve a single supported calendar date for a graph query."""
import re
from datetime import date, datetime, time, timedelta, timezone

from app.schemas.questions import QuestionTimeScope


CALENDAR_ZONE = timezone(timedelta(hours=8))
DATE_OR_DAY = re.compile(
    r'(?<!\d)(?:(?P<iso_year>[0-9]{4})[-－](?P<iso_month>[0-9]{1,2})[-－](?P<iso_day>[0-9]{1,2})(?!\d)'
    r'|(?P<cn_year>[0-9]{4})\s*年\s*(?P<cn_month>[0-9]{1,2})\s*月\s*(?P<cn_day>[0-9]{1,2})\s*[日号]'
    r'|(?P<relative>今天|今日|昨天|昨日|\btoday\b|\byesterday\b))',
    re.IGNORECASE,
)
AMBIGUOUS = re.compile(
    r'[0-9]{1,2}\s*月(?:\s*[0-9]{1,2}\s*[日号]?)?|[0-9]{4}\s*年|\b[0-9]{4}[/.-][0-9]{1,2}(?:[/.-][0-9]{1,2})?\b'
    r'|去年|今年|明年|前天|明天|后天|[上下本这](?:周|月|个月|季度)|最近|近期|此前|以前|过去|当时|之前|之后|截至|切换前后|迁移前后'
    r'|(?:上次|首次|最近一次|上一次).{0,18}(?:前|后|时)|(?:迁移|切换|上线|发布|重构|升级)(?:前|后|时)'
    r'|\b(?:last|this|next)\s+(?:week|month|year)\b|\b(?:before|after)\s+(?:the\s+)?(?:last\s+)?(?:migration|switch|release)\b',
    re.IGNORECASE,
)
PRECISION = re.compile(
    r'^\s*(?:T[0-9]|[0-9]{1,2}\s*[:：时点]|凌晨|上午|中午|下午|晚上|[至到~～—–-]\s*[0-9])',
    re.IGNORECASE,
)


def resolve_question_time(question: str, explicit: datetime | None, reference: datetime) -> QuestionTimeScope:
    if explicit is not None:
        return QuestionTimeScope(source='manual', valid_at=explicit.astimezone(timezone.utc))
    matches = list(DATE_OR_DAY.finditer(question))
    if not matches and not AMBIGUOUS.search(question):
        return QuestionTimeScope(source='current', valid_at=reference)
    if len(matches) == 1:
        match = matches[0]
        remainder = question[:match.start()] + ' ' + question[match.end():]
        if not AMBIGUOUS.search(remainder) and not PRECISION.match(question[match.end():]):
            try:
                values = match.groupdict()
                if values['relative']:
                    if values['relative'].lower() in {'今天', '今日', 'today'}:
                        return QuestionTimeScope(source='question', valid_at=reference, expression=match[0])
                    day = reference.astimezone(CALENDAR_ZONE).date() - timedelta(days=1)
                else:
                    kind = 'iso' if values['iso_year'] else 'cn'
                    day = date(*(int(match[f'{kind}_{part}']) for part in ('year', 'month', 'day')))
                return QuestionTimeScope(source='question', valid_at=datetime.combine(day, time.min, timezone.utc),
                                         expression=match[0])
            except (ValueError, OverflowError):
                pass
    return QuestionTimeScope(source='clarification', valid_at=None)
