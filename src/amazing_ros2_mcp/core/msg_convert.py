"""Convert ROS 2 messages to Python dicts and back.

Handles nested messages, arrays, and special types (Time, Duration).
"""

import json
from typing import Any


def msg_to_dict(msg: Any) -> dict:
    """Convert a ROS 2 message instance to a Python dict.

    Recursively handles nested messages, lists, and primitive types.
    """
    if msg is None:
        return {}

    # Use get_fields_and_field_types if available (standard rosidl pattern)
    if hasattr(msg, "get_fields_and_field_types"):
        result = {}
        for field_name in msg.get_fields_and_field_types():
            value = getattr(msg, field_name, None)
            result[field_name] = _convert_value(value)
        return result

    # Fallback: use __slots__ (older pattern)
    if hasattr(msg, "__slots__"):
        result = {}
        for slot in msg.__slots__:
            # Strip leading underscore used in some ROS2 msg definitions
            attr_name = slot.lstrip("_")
            value = getattr(msg, attr_name, None)
            result[attr_name] = _convert_value(value)
        return result

    # If it's already a primitive, return as-is
    return msg


def _convert_value(value: Any) -> Any:
    """Convert a single value from a ROS message field."""
    if value is None:
        return None

    # Primitives
    if isinstance(value, (bool, int, float, str)):
        return value

    # Bytes → list of ints (for images, etc.)
    if isinstance(value, (bytes, bytearray)):
        return list(value)

    # Lists/tuples/arrays
    if isinstance(value, (list, tuple)):
        return [_convert_value(v) for v in value]

    # Numpy arrays (common in sensor msgs)
    if hasattr(value, "tolist"):
        return value.tolist()

    # Nested ROS message
    if hasattr(value, "get_fields_and_field_types") or hasattr(value, "__slots__"):
        return msg_to_dict(value)

    # Fallback: try str
    return str(value)


def safe_json_dumps(obj: Any, indent: int = 2) -> str:
    """JSON serialize with fallback for non-serializable types."""
    try:
        return json.dumps(obj, indent=indent, default=str)
    except (TypeError, ValueError) as exc:
        return json.dumps(
            {"error": "JSON serialization failed", "message": str(exc)},
            indent=indent,
        )
