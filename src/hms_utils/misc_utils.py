from typing import Any


def is_primitive_type(value: Any) -> bool:  # noqa
    return isinstance(value, (int, float, str, bool))
