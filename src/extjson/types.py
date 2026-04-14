"""Minimal BSON-style extended types. Vendors just enough for v0."""
import os
import re
import struct
import time


_OID_RE = re.compile(r"^[0-9a-fA-F]{24}$")


class ObjectId:
    """12-byte MongoDB ObjectId. Hex string of length 24 on the wire.

    Not bit-compatible with pymongo's counter/process-id scheme — we use a
    simple timestamp+random pattern. For v0 that is enough: uniqueness is
    the only contract clients rely on.
    """

    __slots__ = ("_bytes",)

    def __init__(self, value=None):
        if value is None:
            self._bytes = self._generate()
        elif isinstance(value, ObjectId):
            self._bytes = value._bytes
        elif isinstance(value, (bytes, bytearray)):
            if len(value) != 12:
                raise ValueError(f"ObjectId requires 12 bytes, got {len(value)}")
            self._bytes = bytes(value)
        elif isinstance(value, str):
            if not _OID_RE.match(value):
                raise ValueError(f"invalid ObjectId string: {value!r}")
            self._bytes = bytes.fromhex(value)
        else:
            raise TypeError(f"cannot construct ObjectId from {type(value).__name__}")

    @staticmethod
    def _generate():
        ts = struct.pack(">I", int(time.time()) & 0xFFFFFFFF)
        rnd = os.urandom(8)
        return ts + rnd

    def __str__(self):
        return self._bytes.hex()

    def __repr__(self):
        return f"ObjectId({str(self)!r})"

    def __eq__(self, other):
        if isinstance(other, ObjectId):
            return self._bytes == other._bytes
        return NotImplemented

    def __hash__(self):
        return hash(self._bytes)

    def __json__(self):
        return {"$oid": str(self)}

    @classmethod
    def from_json(cls, obj):
        return cls(obj["$oid"])
