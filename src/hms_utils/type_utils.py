from typing import Any, Optional

primitive_type = (int, float, str, bool)


def is_primitive_type(value: Any) -> bool:
    return isinstance(value, primitive_type)


def is_integer(value: str) -> bool:
    if isinstance(value, str) and (value := value.strip()):
        try:
            int(value)
        except Exception:
            pass
    return False


def to_integer(value: str) -> Optional[int]:
    if isinstance(value, str) and (value := value.strip()):
        try:
            return int(value)
        except Exception:
            pass
    return None


def any_of_bool(*booleans) -> bool:
    for boolean in booleans:
        if boolean is True:
            return True
    return False


def at_most_one_of_bool(*booleans) -> bool:
    ntrue = 0
    for boolean in booleans:
        if boolean is True:
            if ntrue > 0:
                return False
            ntrue += 1
    return True
