from datetime import datetime, timedelta, timezone, time
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

UTC = timezone.utc


def now_iso():
    return datetime.now(UTC).isoformat()


def parse_date(value, zone='UTC'):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).strip().replace('Z', '+00:00'))
    except ValueError:
        try:
            dt = parsedate_to_datetime(str(value))
        except (ValueError, TypeError, OverflowError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(zone))
    return dt.astimezone(UTC)


def normalized(value, zone='UTC'):
    dt = parse_date(value, zone)
    return dt.isoformat() if dt else None


def period(kind, now, zone='Europe/Rome'):
    tz = ZoneInfo(zone)
    today = now.astimezone(tz).date()
    end = today if kind == 'daily' else today - timedelta(days=today.weekday())
    start = end - timedelta(days=1 if kind == 'daily' else 7)
    return (datetime.combine(start, time(), tz).astimezone(UTC),
            datetime.combine(end, time(), tz).astimezone(UTC))


def scheduled(day, clock, zone):
    return datetime.combine(day, time.fromisoformat(clock), ZoneInfo(zone))
