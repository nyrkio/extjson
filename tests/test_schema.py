import pytest
from extjson import validate, resolve_schema, ValidationError, SchemaError


def test_type_string():
    validate("hi", {"type": "string"})
    with pytest.raises(ValidationError):
        validate(5, {"type": "string"})


def test_type_integer_rejects_bool():
    # bool is not integer in this validator (MongoDB-ish)
    with pytest.raises(ValidationError):
        validate(True, {"type": "integer"})
    validate(5, {"type": "integer"})


def test_object_required_and_properties():
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name"],
    }
    validate({"name": "Ada", "age": 37}, schema)
    validate({"name": "Ada"}, schema)  # age optional
    with pytest.raises(ValidationError):
        validate({"age": 37}, schema)  # missing name


def test_additional_properties_defaults_true():
    schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
    # "extra" not in properties, should be allowed by default (MongoDB-like).
    validate({"x": 1, "extra": "whatever"}, schema)


def test_additional_properties_false_rejects():
    schema = {
        "type": "object",
        "properties": {"x": {"type": "integer"}},
        "additionalProperties": False,
    }
    with pytest.raises(ValidationError):
        validate({"x": 1, "extra": "nope"}, schema)


def test_array_items():
    schema = {"type": "array", "items": {"type": "integer"}}
    validate([1, 2, 3], schema)
    with pytest.raises(ValidationError):
        validate([1, "two", 3], schema)


def test_enum():
    schema = {"enum": ["a", "b", "c"]}
    validate("a", schema)
    with pytest.raises(ValidationError):
        validate("d", schema)


def test_pattern_and_lengths():
    schema = {"type": "string", "pattern": "^abc", "minLength": 3, "maxLength": 10}
    validate("abc", schema)
    validate("abcdefg", schema)
    with pytest.raises(ValidationError):
        validate("abcdefghijk", schema)  # too long
    with pytest.raises(ValidationError):
        validate("xyzabc", schema)  # pattern miss


def test_extends_simple():
    registry = {
        "Person": {
            "$id": "Person",
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
        "Employee": {
            "$id": "Employee",
            "$extends": "Person",
            "properties": {"employee_id": {"type": "string"}},
            "required": ["employee_id"],
        },
    }
    resolved = resolve_schema(registry["Employee"], registry)
    assert set(resolved["required"]) == {"name", "employee_id"}
    assert "name" in resolved["properties"]
    assert "employee_id" in resolved["properties"]

    validate({"name": "Ada", "employee_id": "E1"}, "Employee", registry)
    with pytest.raises(ValidationError):
        validate({"employee_id": "E1"}, "Employee", registry)  # missing inherited required


def test_extends_multi_level():
    registry = {
        "A": {"$id": "A", "type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"]},
        "B": {"$id": "B", "$extends": "A", "properties": {"b": {"type": "integer"}}, "required": ["b"]},
        "C": {"$id": "C", "$extends": "B", "properties": {"c": {"type": "integer"}}, "required": ["c"]},
    }
    validate({"a": 1, "b": 2, "c": 3}, "C", registry)
    with pytest.raises(ValidationError):
        validate({"b": 2, "c": 3}, "C", registry)  # missing A's required


def test_extends_child_overrides_type_hint():
    # Child can tighten: parent says additionalProperties default True, child sets False.
    registry = {
        "Parent": {"$id": "Parent", "type": "object", "properties": {"x": {"type": "integer"}}},
        "StrictChild": {"$id": "StrictChild", "$extends": "Parent", "additionalProperties": False},
    }
    validate({"x": 1}, "StrictChild", registry)
    with pytest.raises(ValidationError):
        validate({"x": 1, "y": 2}, "StrictChild", registry)


def test_unknown_schema_id_raises():
    with pytest.raises(SchemaError):
        validate({"a": 1}, "Nonexistent", {})


def test_purejson_document_validates():
    from purejson import Document
    schema = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]}
    validate(Document({"x": 5}), schema)
