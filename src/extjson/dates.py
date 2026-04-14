"""Strict UTC-aware datetime helpers. Naive datetimes are programmer errors
in this codebase — they fail loudly at boundaries instead of being silently
promoted to UTC (which hides real bugs)."""
import datetime


UTC = datetime.timezone.utc


class NaiveDatetimeError(ValueError):
    """A naive datetime (tzinfo is None) was passed where aware is required."""


def utcnow():
    """Current time as an aware UTC datetime."""
    return datetime.datetime.now(UTC)


def to_utc(dt):
    """Return an aware UTC datetime. Raises NaiveDatetimeError on naive input.

    Use this at any boundary that ingests a datetime from potentially-untrusted
    code. If you know a datetime should be local-time-assumed-UTC, promote it
    explicitly at the call site with `dt.replace(tzinfo=timezone.utc)` — never
    silently here.
    """
    if not isinstance(dt, datetime.datetime):
        raise TypeError(f"expected datetime, got {type(dt).__name__}")
    if dt.tzinfo is None:
        raise NaiveDatetimeError(
            "naive datetime (tzinfo is None) is not accepted. Use "
            "extjson.utcnow() for current time, extjson.parse_date() for "
            "strings, or explicitly set tzinfo at the call site."
        )
    return dt.astimezone(UTC)


def parse_date(s):
    """Parse an ISO-8601 string or a {'$date': '...'} dict into aware UTC.

    Raises NaiveDatetimeError if the input carries no timezone.
    """
    if isinstance(s, dict):
        if "$date" not in s or len(s) != 1:
            raise ValueError(f"expected single-key $date dict, got {s!r}")
        s = s["$date"]
    if not isinstance(s, str):
        raise TypeError(f"expected string or $date dict, got {type(s).__name__}")
    normalized = s[:-1] + "+00:00" if s.endswith("Z") else s
    dt = datetime.datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        raise NaiveDatetimeError(
            f"datetime string {s!r} has no timezone offset. ISO-8601 inputs "
            "must end in 'Z' or an explicit ±HH:MM offset."
        )
    return dt.astimezone(UTC)
