"""Minimal JSON Schema (2020-12 subset) validator for MCP tool arguments.

Supports exactly the keywords used by medagent's tool schemas (``type``,
``enum``, ``const``, ``anyOf``, string/number/array bounds, ``pattern``,
``properties``, ``required`` and ``additionalProperties``) so the advertised
``inputSchema`` is also the single source of truth for argument validation
without adding a runtime dependency. Schemas are static and trusted; there is
no ``$ref`` resolution.
"""

from __future__ import annotations

import re
from typing import Any

_PYTHON_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "boolean": (bool,),
    "null": (type(None),),
}


def _matches_type(value: Any, expected: str) -> bool:
    """Return True when ``value`` is an instance of the JSON type ``expected``."""
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _PYTHON_TYPES[expected])


def _declared_types(schema: dict[str, Any]) -> list[str]:
    """Return the JSON types a (sub)schema declares, if any."""
    declared = schema.get("type")
    if declared is None:
        return []
    return list(declared) if isinstance(declared, list) else [declared]


def validate(instance: Any, schema: dict[str, Any], path: str = "arguments") -> list[str]:
    """Validate ``instance`` against ``schema``.

    Args:
        instance: Decoded JSON value to check.
        schema: JSON Schema using the supported keyword subset.
        path: Human-readable location used as the prefix of error messages.

    Returns:
        Validation error messages; empty when ``instance`` is valid.
    """
    if "anyOf" in schema:
        branches: list[dict[str, Any]] = schema["anyOf"]
        if any(not validate(instance, branch, path) for branch in branches):
            return []
        typed = [
            branch
            for branch in branches
            if any(_matches_type(instance, t) for t in _declared_types(branch))
        ]
        if typed:
            return validate(instance, typed[0], path)
        allowed = sorted({t for branch in branches for t in _declared_types(branch)})
        return [f"{path} must be of type {' or '.join(allowed)}"]

    types = _declared_types(schema)
    if types and not any(_matches_type(instance, t) for t in types):
        return [f"{path} must be of type {' or '.join(types)}"]

    errors: list[str] = []
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path} must be one of {schema['enum']!r}")

    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            errors.append(f"{path} must be at least {schema['minLength']} character(s)")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path} must be at most {schema['maxLength']} characters")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path} must match pattern {schema['pattern']!r}")
    elif _matches_type(instance, "number"):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path} must be >= {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path} must be <= {schema['maximum']}")
    elif isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            errors.append(f"{path} must contain at least {schema['minItems']} item(s)")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path} must contain at most {schema['maxItems']} items")
        if "items" in schema:
            for index, item in enumerate(instance):
                errors.extend(validate(item, schema["items"], f"{path}[{index}]"))
    elif isinstance(instance, dict):
        properties: dict[str, Any] = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in instance:
                errors.append(f"{path}.{name} is required")
        for name, value in instance.items():
            if name in properties:
                errors.extend(validate(value, properties[name], f"{path}.{name}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}.{name} is not an allowed property")
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(validate(value, schema["additionalProperties"], f"{path}.{name}"))
    return errors
