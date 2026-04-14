import datetime
import pytest
from extjson import utcnow, to_utc, parse_date, NaiveDatetimeError, UTC, validate, ValidationError


def test_utcnow_is_aware_utc():
    dt = utcnow()
    assert dt.tzinfo is not None
    assert dt.utcoffset() == datetime.timedelta(0)


def test_to_utc_rejects_naive():
    with pytest.raises(NaiveDatetimeError):
        to_utc(datetime.datetime(2026, 4, 14, 12, 0, 0))


def test_to_utc_converts_aware_offset():
    east = datetime.timezone(datetime.timedelta(hours=3))
    dt = datetime.datetime(2026, 4, 14, 12, 0, 0, tzinfo=east)
    result = to_utc(dt)
    assert result.tzinfo == UTC
    assert result == dt  # same instant


def test_to_utc_rejects_non_datetime():
    with pytest.raises(TypeError):
        to_utc("2026-04-14")


def test_parse_date_iso_with_z():
    dt = parse_date("2026-04-14T12:00:00Z")
    assert dt.tzinfo == UTC
    assert dt == datetime.datetime(2026, 4, 14, 12, 0, 0, tzinfo=UTC)


def test_parse_date_iso_with_offset():
    dt = parse_date("2026-04-14T15:00:00+03:00")
    assert dt.tzinfo == UTC
    assert dt == datetime.datetime(2026, 4, 14, 12, 0, 0, tzinfo=UTC)


def test_parse_date_rejects_naive_iso():
    with pytest.raises(NaiveDatetimeError):
        parse_date("2026-04-14T12:00:00")


def test_parse_date_accepts_dollar_date_dict():
    dt = parse_date({"$date": "2026-04-14T12:00:00Z"})
    assert dt.tzinfo == UTC


def test_parse_date_rejects_malformed_dollar_date():
    with pytest.raises(ValueError):
        parse_date({"$date": "2026-04-14T12:00:00Z", "extra": "bad"})


def test_schema_date_type_accepts_aware():
    dt_aware = utcnow()
    validate(dt_aware, {"type": "date"})


def test_schema_date_type_rejects_naive():
    dt_naive = datetime.datetime(2026, 4, 14, 12, 0, 0)
    with pytest.raises(ValidationError):
        validate(dt_naive, {"type": "date"})
