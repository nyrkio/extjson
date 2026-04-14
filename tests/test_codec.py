import datetime
import pytest
from extjson import dumps, loads, ObjectId, register_type


def test_plain_json_round_trip():
    obj = {"a": 1, "b": [1, 2, 3], "c": {"d": "e"}}
    assert loads(dumps(obj)) == obj


def test_oid_round_trip():
    oid = ObjectId()
    wire = dumps({"_id": oid})
    assert '"$oid"' in wire
    parsed = loads(wire)
    assert parsed == {"_id": oid}
    assert isinstance(parsed["_id"], ObjectId)


def test_oid_from_hex():
    oid = ObjectId("507f1f77bcf86cd799439011")
    assert str(oid) == "507f1f77bcf86cd799439011"


def test_oid_equality_and_hash():
    a = ObjectId("507f1f77bcf86cd799439011")
    b = ObjectId("507f1f77bcf86cd799439011")
    c = ObjectId("507f1f77bcf86cd799439012")
    assert a == b
    assert a != c
    assert hash(a) == hash(b)
    assert {a, b, c} == {a, c}


def test_oid_invalid_hex_rejected():
    with pytest.raises(ValueError):
        ObjectId("not-hex")
    with pytest.raises(ValueError):
        ObjectId("507f1f77")  # too short


def test_datetime_round_trip_utc():
    dt = datetime.datetime(2026, 4, 14, 12, 0, 0, tzinfo=datetime.timezone.utc)
    wire = dumps({"at": dt})
    assert '"$date"' in wire
    parsed = loads(wire)
    assert parsed == {"at": dt}


def test_datetime_naive_becomes_utc():
    dt_naive = datetime.datetime(2026, 4, 14, 12, 0, 0)
    wire = dumps({"at": dt_naive})
    parsed = loads(wire)
    assert parsed["at"].tzinfo is not None


def test_long_marker_for_large_ints():
    big = 2**60
    wire = dumps({"n": big})
    assert "$long" in wire
    parsed = loads(wire)
    assert parsed == {"n": big}


def test_small_ints_stay_plain():
    wire = dumps({"n": 42})
    assert "$long" not in wire
    assert loads(wire) == {"n": 42}


def test_purejson_document_normalizes():
    from purejson import Document
    d = Document({"a": 1, "nested": {"b": 2}})
    wire = dumps(d)
    assert loads(wire) == {"a": 1, "nested": {"b": 2}}


def test_purejson_collection_normalizes():
    from purejson import Collection
    c = Collection([{"a": 1}, {"a": 2}])
    wire = dumps(c)
    assert loads(wire) == [{"a": 1}, {"a": 2}]


def test_custom_type_register():
    class Point:
        def __init__(self, x, y):
            self.x, self.y = x, y
        def __json__(self):
            return {"$point": {"x": self.x, "y": self.y}}
        @classmethod
        def from_json(cls, obj):
            return cls(obj["$point"]["x"], obj["$point"]["y"])
        def __eq__(self, other):
            return isinstance(other, Point) and (self.x, self.y) == (other.x, other.y)
        def __hash__(self):
            return hash((self.x, self.y))

    register_type("$point", Point)
    p = Point(3, 4)
    wire = dumps({"p": p})
    assert "$point" in wire
    parsed = loads(wire)
    assert parsed == {"p": p}
