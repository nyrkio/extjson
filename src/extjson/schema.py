"""Minimal JSON Schema validator (Draft-7 subset) with `$extends` inheritance.

Supported keywords: type, properties, required, additionalProperties,
items, enum, minimum, maximum, minLength, maxLength, pattern. Plus
`$extends` (string: $id of parent schema, or inline schema dict).
"""
import datetime
import re
from .types import ObjectId


class SchemaError(Exception):
    """Problem with the schema itself."""


class ValidationError(Exception):
    """Data does not conform."""

    def __init__(self, message, path=None):
        super().__init__(message)
        self.path = path or []

    def __str__(self):
        loc = "/".join(str(p) for p in self.path) or "<root>"
        return f"{self.args[0]} at {loc}"


_TYPE_CHECKERS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict) or hasattr(v, "data"),
    "null": lambda v: v is None,
    "objectid": lambda v: isinstance(v, ObjectId),
    "date": lambda v: isinstance(v, datetime.datetime),
}


def resolve_schema(schema, registry):
    """Walk the $extends chain and produce a flattened schema.

    `registry` maps $id -> raw schema dict. `schema` may be a dict or a string
    (interpreted as a $id lookup).
    """
    if isinstance(schema, str):
        if schema not in registry:
            raise SchemaError(f"unknown schema $id: {schema!r}")
        schema = registry[schema]
    if "$extends" not in schema:
        return schema

    parent_ref = schema["$extends"]
    parent = resolve_schema(parent_ref, registry)

    merged = {
        "type": schema.get("type", parent.get("type")),
        "properties": {**parent.get("properties", {}), **schema.get("properties", {})},
        "required": list(dict.fromkeys(parent.get("required", []) + schema.get("required", []))),
    }
    # Carry over other keywords; child overrides parent.
    for k in ("additionalProperties", "items", "enum", "minimum", "maximum",
              "minLength", "maxLength", "pattern"):
        if k in schema:
            merged[k] = schema[k]
        elif k in parent:
            merged[k] = parent[k]
    if "$id" in schema:
        merged["$id"] = schema["$id"]
    return merged


def validate(data, schema, registry=None):
    """Validate `data` against `schema`. Raises ValidationError on failure.

    `registry` is a dict of $id -> schema for `$extends` resolution.
    """
    registry = registry or {}
    resolved = resolve_schema(schema, registry)
    _validate(data, resolved, registry, path=[])


def _unwrap(obj):
    if hasattr(obj, "data") and not isinstance(obj, (str, bytes, bytearray)):
        return obj.data
    return obj


def _validate(data, schema, registry, path):
    data = _unwrap(data)

    t = schema.get("type")
    if t is not None:
        checkers = [t] if isinstance(t, str) else t
        if not any(_TYPE_CHECKERS.get(c, lambda v: False)(data) for c in checkers):
            raise ValidationError(f"expected type {t}, got {type(data).__name__}", path)

    if "enum" in schema and data not in schema["enum"]:
        raise ValidationError(f"value {data!r} not in enum {schema['enum']}", path)

    if isinstance(data, str):
        if "minLength" in schema and len(data) < schema["minLength"]:
            raise ValidationError(f"string shorter than minLength {schema['minLength']}", path)
        if "maxLength" in schema and len(data) > schema["maxLength"]:
            raise ValidationError(f"string longer than maxLength {schema['maxLength']}", path)
        if "pattern" in schema and not re.search(schema["pattern"], data):
            raise ValidationError(f"string does not match pattern {schema['pattern']!r}", path)

    if isinstance(data, (int, float)) and not isinstance(data, bool):
        if "minimum" in schema and data < schema["minimum"]:
            raise ValidationError(f"value {data} < minimum {schema['minimum']}", path)
        if "maximum" in schema and data > schema["maximum"]:
            raise ValidationError(f"value {data} > maximum {schema['maximum']}", path)

    if isinstance(data, dict):
        props = schema.get("properties", {})
        required = schema.get("required", [])
        for key in required:
            if key not in data:
                raise ValidationError(f"missing required property {key!r}", path)
        # additionalProperties defaults to True per the PLAN (MongoDB-like).
        additional = schema.get("additionalProperties", True)
        for key, val in data.items():
            if key in props:
                sub = resolve_schema(props[key], registry) if isinstance(props[key], (dict, str)) else props[key]
                _validate(val, sub, registry, path + [key])
            else:
                if additional is False:
                    raise ValidationError(f"additional property {key!r} not allowed", path)
                elif isinstance(additional, dict):
                    _validate(val, additional, registry, path + [key])

    if isinstance(data, list):
        if "items" in schema:
            item_schema = resolve_schema(schema["items"], registry) if isinstance(schema["items"], (dict, str)) else schema["items"]
            for i, item in enumerate(data):
                _validate(item, item_schema, registry, path + [i])
