"""Extended JSON encoding/decoding. Handles BSON-style $oid/$date/$long plus
pluggable custom types via __json__ / from_json."""
import json
import datetime
from .types import ObjectId
from .dates import NaiveDatetimeError

try:
    from bson import ObjectId as _BsonObjectId
except ImportError:
    _BsonObjectId = None


_TYPE_REGISTRY = {}  # {"$oid": ObjectId, "$date": datetime, ...}


def register_type(tag, cls):
    """Register a class for a $tag marker. `cls` must have a classmethod
    `from_json(obj)` and instances must have `__json__()`."""
    _TYPE_REGISTRY[tag] = cls


register_type("$oid", ObjectId)


class _DateTimeAdapter:
    """Internal adapter so datetime (stdlib) participates without subclassing."""

    @staticmethod
    def to_json(dt):
        if dt.tzinfo is None:
            raise NaiveDatetimeError(
                "refusing to serialize naive datetime. Use extjson.utcnow() or "
                "extjson.to_utc(dt) to produce an aware value at the call site."
            )
        # Preserve the caller's offset on the wire. ISO-8601 can't encode zone
        # identity (e.g. "Europe/Helsinki") — only the offset — but that's all
        # a round-trip needs. Callers who want UTC canonicalization should do
        # it explicitly (extjson.to_utc) before serializing.
        s = dt.isoformat()
        # Use 'Z' for zero offset to match MongoDB relaxed Extended JSON.
        if s.endswith("+00:00"):
            s = s[:-6] + "Z"
        return {"$date": s}

    @staticmethod
    def from_json(obj):
        s = obj["$date"]
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            raise NaiveDatetimeError(
                f"$date wire value {obj!r} carries no timezone offset"
            )
        return dt


class _LongAdapter:
    """Ints larger than JS-safe range are emitted as {"$long": "123..."} to
    preserve precision through any consumer that might treat numbers as
    floats. v0 threshold: 2^53."""

    SAFE_MAX = (1 << 53) - 1
    SAFE_MIN = -(1 << 53)

    @staticmethod
    def maybe_to_json(n):
        if isinstance(n, bool):
            return None
        if isinstance(n, int) and (n > _LongAdapter.SAFE_MAX or n < _LongAdapter.SAFE_MIN):
            return {"$long": str(n)}
        return None

    @staticmethod
    def from_json(obj):
        return int(obj["$long"])


def _encode_default(obj):
    # PureJson objects: unwrap to .data
    if hasattr(obj, "data") and not isinstance(obj, (bytes, bytearray)):
        return obj.data
    # Custom type with __json__
    if hasattr(obj, "__json__"):
        return obj.__json__()
    # bson.ObjectId from pymongo/secantusdb — same wire format as extjson.ObjectId
    if _BsonObjectId is not None and isinstance(obj, _BsonObjectId):
        return {"$oid": str(obj)}
    # datetime
    if isinstance(obj, datetime.datetime):
        return _DateTimeAdapter.to_json(obj)
    if isinstance(obj, datetime.date) and not isinstance(obj, datetime.datetime):
        # Pure date (no time) promotes to midnight UTC — explicit, not silent, and
        # only because a date literally cannot carry a timezone.
        return _DateTimeAdapter.to_json(datetime.datetime(obj.year, obj.month, obj.day, tzinfo=datetime.timezone.utc))
    raise TypeError(f"extjson cannot encode object of type {type(obj).__name__}")


def _walk_encode_ints(obj):
    """Post-walk to convert out-of-safe-range ints into $long markers."""
    if isinstance(obj, dict):
        return {k: _walk_encode_ints(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_encode_ints(v) for v in obj]
    if isinstance(obj, int) and not isinstance(obj, bool):
        marker = _LongAdapter.maybe_to_json(obj)
        if marker is not None:
            return marker
    return obj


def dumps(obj, **kwargs):
    # First pass: let json resolve custom types / PureJson wrappers via default.
    # json.dumps calls default only for non-serializable types, so we need to
    # normalize PureJson containers and datetimes up front.
    normalized = _normalize(obj)
    normalized = _walk_encode_ints(normalized)
    return json.dumps(normalized, **kwargs)


def _normalize(obj):
    # PureJson Document/Collection
    if hasattr(obj, "data") and not isinstance(obj, (bytes, bytearray, str)):
        return _normalize(obj.data)
    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize(v) for v in obj]
    if hasattr(obj, "__json__"):
        return _normalize(obj.__json__())
    if _BsonObjectId is not None and isinstance(obj, _BsonObjectId):
        return {"$oid": str(obj)}
    if isinstance(obj, datetime.datetime):
        return _DateTimeAdapter.to_json(obj)
    if isinstance(obj, datetime.date) and not isinstance(obj, datetime.datetime):
        return _DateTimeAdapter.to_json(datetime.datetime(obj.year, obj.month, obj.day, tzinfo=datetime.timezone.utc))
    return obj


def _object_hook(obj):
    if len(obj) == 1:
        (only_key,) = obj.keys()
        if only_key == "$date":
            return _DateTimeAdapter.from_json(obj)
        if only_key == "$long":
            return _LongAdapter.from_json(obj)
        cls = _TYPE_REGISTRY.get(only_key)
        if cls is not None:
            return cls.from_json(obj)
    return obj


def loads(s, **kwargs):
    return json.loads(s, object_hook=_object_hook, **kwargs)
