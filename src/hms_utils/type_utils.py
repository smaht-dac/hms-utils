from typing import Any

primitive_type = (int, float, str, bool)


def is_primitive_type(value: Any) -> bool:
    return isinstance(value, primitive_type)


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
