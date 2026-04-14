# ExtendedJsonSchema — PLAN

## Purpose
Drop-in extension/replacement for stdlib `json` and the `jsonschema` package, adding:
1. **Inheritance** as a first-class JSON Schema concept (`$extends`).
2. **MongoDB extended types** ($oid, $date, $long, $decimal, $binary, $regex, $timestamp) as standard types.
3. Python-type mapping that matches `pymongo`'s, so a doc round-trips PureJson → DocumentDB → PureJson identically.

## Inheritance model

Use `$extends` (JSON-native naming, dropping the XML-flavored `xs:*` prefix). Even what XML would call a "restriction" is conceptually still an extension of a parent spec — there's no useful distinction at this level.

```json
{
  "$id": "Employee",
  "$extends": "Person",
  "properties": { "employee_id": {"type": "string"} }
}
```

Resolution: validator walks the `$extends` chain, merges `properties` and `required`, then applies the child's own constraints on top.

**`additionalProperties` defaults to `true`.** Like MongoDB, the goal is partial schemas — an object may declare *some* of its properties without forbidding others. A schema that wants strict shape opts in by setting `additionalProperties: false`.

## Extended type registry

Wire format: BSON-style `{"$oid": "..."}`, `{"$date": "..."}`, etc. Python mapping matches pymongo: `bson.ObjectId`, `datetime.datetime` (UTC), `int` (range-checked for $long), `decimal.Decimal`, `bytes`, `re.Pattern`.

**Custom types declare their own eJson representation.** A type defines how it serializes:

```python
class Point:
    def __json__(self):
        return {"$point": {"x": self.x, "y": self.y}}

p = Point(3, 4)
extjson.dumps(p) == json.dumps(p.__json__())
```

This keeps the encoder pluggable without a separate registry — types own their wire format. Inverse is symmetric: a class can declare a `from_json` classmethod that the decoder calls when it sees the matching `$type` key.

## $ref — probably not needed

JSON Schema's `$ref` is frequently a workaround for the lack of native parent/child relationships. Once `$extends` exists as a first-class concept, most `$ref` use cases evaporate. Defer `$ref` indefinitely; revisit only if a real use case appears that `$extends` can't cover.

## API surface

```python
from extjson import dumps, loads, validate, schema_from_dict
```
Mirrors stdlib `json` + `jsonschema.validate` so existing code can swap imports.

## Non-goals
- Not aiming for full Draft 2020-12 conformance day one; target Draft 7 + the extensions above. Doc the gap.

## Dependencies
- `bson` (or vendor the ObjectId implementation — it's ~50 lines).
- No `jsonschema` package dependency; we re-implement the validator (it's small for Draft 7).

## Open questions — need worked examples for each

1. **`$extends` semantics edge cases** — what does it mean to extend a schema whose parent has `additionalProperties: false`? Loosening should be possible by the child re-declaring it `true`. Need an example.
2. **Schema versioning** — should schemas declare `$schema_version` for migration tooling? Need an example of a v1 → v2 migration to know what tooling actually needs to do.
3. **`$extends` × `oneOf` / `anyOf`** — what happens when a child extends a parent that uses `oneOf`? Need a worked example before specifying.
