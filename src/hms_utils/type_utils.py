from typing import Any, List, Optional, Tuple, Union

primitive_type = (int, float, str, bool)


def is_primitive_type(value: Any) -> bool:
    return isinstance(value, primitive_type)


def is_integer(value: str) -> bool:
    return to_integer(value) is not None


def to_integer(value: str) -> Optional[int]:
    if isinstance(value, str) and (value := value.strip()):
        try:
            return int(value)
        except Exception:
            pass
    return None


def is_float(value: str) -> bool:
    return to_float(value) is not None


def to_float(value: str) -> Optional[int]:
    if isinstance(value, str) and (value := value.strip()):
        try:
            return float(value)
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


def to_non_empty_string_list(value: Union[List[str], Tuple[str, ...], str], strip: bool = True) -> List[str]:
    strings = []
    if isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, str) and ((strip is False) or (item := item.strip())):
                strings.append(item)
    elif isinstance(value, str) and ((strip is False) or (value := value.strip())):
        strings = [value]
    return strings
