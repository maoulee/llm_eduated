"""Tool base class.

Adapted from DeepTutor's Apache-2.0 licensed tutorbot agent tool protocol.
The 408 system keeps this local copy small so the runtime can evolve without
pulling in DeepTutor's full bot/channel/web stack.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypeAlias


class Tool(ABC):
    """Base class for tools exposed to an agent loop."""

    _ClassInfo: TypeAlias = type[Any] | tuple[type[Any], ...]

    _TYPE_MAP: dict[str, _ClassInfo] = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name used in function calls."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Short description for the model."""

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON schema for parameters."""

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool and return a string observation."""

    def cast_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Apply conservative schema-driven casts before validation."""
        schema = self.parameters or {}
        if schema.get("type", "object") != "object":
            return params
        return self._cast_object(params, schema)

    def _cast_object(self, obj: Any, schema: dict[str, Any]) -> Any:
        if not isinstance(obj, dict):
            return obj
        props = schema.get("properties", {})
        result: dict[str, Any] = {}
        for key, value in obj.items():
            result[key] = self._cast_value(value, props[key]) if key in props else value
        return result

    def _cast_value(self, val: Any, schema: dict[str, Any]) -> Any:
        target_type = schema.get("type")

        if target_type == "boolean" and isinstance(val, bool):
            return val
        if target_type == "integer" and isinstance(val, int) and not isinstance(val, bool):
            return val
        if target_type in self._TYPE_MAP and target_type not in (
            "boolean",
            "integer",
            "array",
            "object",
        ):
            if isinstance(val, self._TYPE_MAP[target_type]):
                return val

        if target_type == "integer" and isinstance(val, str):
            try:
                return int(val)
            except ValueError:
                return val

        if target_type == "number" and isinstance(val, str):
            try:
                return float(val)
            except ValueError:
                return val

        if target_type == "string":
            return val if val is None else str(val)

        if target_type == "boolean" and isinstance(val, str):
            val_lower = val.lower()
            if val_lower in {"true", "1", "yes"}:
                return True
            if val_lower in {"false", "0", "no"}:
                return False
            return val

        if target_type == "array" and isinstance(val, list):
            item_schema = schema.get("items")
            return [self._cast_value(item, item_schema) for item in val] if item_schema else val

        if target_type == "object" and isinstance(val, dict):
            return self._cast_object(val, schema)

        return val

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate params against the tool's JSON schema."""
        if not isinstance(params, dict):
            return [f"parameters must be an object, got {type(params).__name__}"]
        schema = self.parameters or {}
        if schema.get("type", "object") != "object":
            return [f"schema must be object type, got {schema.get('type')!r}"]
        return self._validate(params, {**schema, "type": "object"}, "")

    def _validate(self, val: Any, schema: dict[str, Any], path: str) -> list[str]:
        type_name = schema.get("type")
        label = path or "parameter"
        errors: list[str] = []

        if type_name == "integer" and (not isinstance(val, int) or isinstance(val, bool)):
            return [f"{label} should be integer"]
        if type_name == "number" and (
            not isinstance(val, self._TYPE_MAP[type_name]) or isinstance(val, bool)
        ):
            return [f"{label} should be number"]
        if (
            type_name in self._TYPE_MAP
            and type_name not in {"integer", "number"}
            and not isinstance(val, self._TYPE_MAP[type_name])
        ):
            return [f"{label} should be {type_name}"]

        if "enum" in schema and val not in schema["enum"]:
            errors.append(f"{label} must be one of {schema['enum']}")

        if type_name in {"integer", "number"}:
            if "minimum" in schema and val < schema["minimum"]:
                errors.append(f"{label} must be >= {schema['minimum']}")
            if "maximum" in schema and val > schema["maximum"]:
                errors.append(f"{label} must be <= {schema['maximum']}")

        if type_name == "string":
            if "minLength" in schema and len(val) < schema["minLength"]:
                errors.append(f"{label} must be at least {schema['minLength']} chars")
            if "maxLength" in schema and len(val) > schema["maxLength"]:
                errors.append(f"{label} must be at most {schema['maxLength']} chars")

        if type_name == "object":
            props = schema.get("properties", {})
            for key in schema.get("required", []):
                if key not in val:
                    errors.append(f"missing required {path + '.' + key if path else key}")
            for key, child in val.items():
                if key in props:
                    child_path = f"{path}.{key}" if path else key
                    errors.extend(self._validate(child, props[key], child_path))

        if type_name == "array" and "items" in schema:
            for index, item in enumerate(val):
                child_path = f"{path}[{index}]" if path else f"[{index}]"
                errors.extend(self._validate(item, schema["items"], child_path))

        return errors

    def to_schema(self) -> dict[str, Any]:
        """Convert this tool to an OpenAI-compatible function schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
