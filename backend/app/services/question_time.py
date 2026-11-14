"""Resolve supported calendar dates for graph questions."""
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
COMPARISON = re.compile(r'对比|比较|相比|什么变化|有何变化|有哪些变化|有什么不同|有什么区别|\bcompare\b', re.I)
CUTOVER = re.compile(r'(?:切换|迁移)前后|\bbefore and after (?:the )?(?:switch|migration)\b', re.I)
GENERIC_CUTOVER = re.compile(
    r'(?:项目的?)?(?:主数据库|数据库|主库)?(?:切换|迁移)前后(?:有(?:什么|何|哪些)变化|有什么不同|有什么区别|分别用什么)?[？?。 ]*',
)


def _calendar_day(match: re.Match) -> date:
    kind = 'iso' if match['iso_year'] else 'cn'
    return date(*(int(match[f'{kind}_{part}']) for part in ('year', 'month', 'day')))


def comparison_dates(question: str) -> tuple[datetime, datetime] | None:
    matches = list(DATE_OR_DAY.finditer(question))
    if len(matches) != 2 or any(match['relative'] for match in matches):
        return None
    # Allow a connector such as "到" between dates, but no appended time precision.
    remainders = [question[:matches[0].start()], question[matches[0].end():matches[1].start()],
                  question[matches[1].end():]]
    if any(PRECISION.match(part) for part in remainders[1:]):
        return None
    if AMBIGUOUS.search(CUTOVER.sub('', ' '.join(remainders))):
        return None
    try:
        first, second = (datetime.combine(_calendar_day(match), time.min, timezone.utc) for match in matches)
    except ValueError:
        return None
    return (min(first, second), max(first, second)) if first != second else None


def uses_reviewed_cutover(question: str) -> bool:
    return bool(CUTOVER.search(question) and not DATE_OR_DAY.search(question)
                and not AMBIGUOUS.search(CUTOVER.sub('', question)))


def resolve_question_time(question: str, explicit: datetime | None, reference: datetime) -> QuestionTimeScope:
    if explicit is not None:
        return QuestionTimeScope(source='manual', valid_at=explicit.astimezone(timezone.utc))
    matches = list(DATE_OR_DAY.finditer(question))
    if CUTOVER.search(question) or (COMPARISON.search(question) and (len(matches) >= 2 or AMBIGUOUS.search(question))):
        return QuestionTimeScope(source='comparison', valid_at=None)
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
                    day = _calendar_day(match)
                return QuestionTimeScope(source='question', valid_at=datetime.combine(day, time.min, timezone.utc),
                                         expression=match[0])
            except (ValueError, OverflowError):
                pass
    return QuestionTimeScope(source='clarification', valid_at=None)
