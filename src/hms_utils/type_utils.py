import re
from typing import Any, List, Optional, Tuple, Union

primitive_type = (int, float, str, bool)
uuid_pattern = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


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


def to_bool(value: str) -> bool:
    return value if isinstance(value, bool) else ((value.strip().lower() == "true")
                                                  if isinstance(value, str) else False)


def to_string_list(value: Union[List[str], Tuple[str, ...], str], strip: bool = True, empty: bool = True) -> List[str]:
    strings = []
    if isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, str):
                if (strip is not False):
                    item = item.strip()
                if (empty is True) or item:
                    strings.append(item)
    elif isinstance(value, str):
        if (strip is not False):
            value = value.strip()
        if (empty is True) or value:
            strings.append(value)
    return strings


def to_non_empty_string_list(value: Union[List[str], Tuple[str, ...], str], strip: bool = True) -> List[str]:
    return to_string_list(value, strip=strip, empty=False)


def is_uuid(value: str) -> bool:
    return uuid_pattern.match(value) if isinstance(value, str) else False


def to_flattened_list(*args) -> List[Any]:
    flattened_list = []
    def flatten(arg):  # noqa
        if isinstance(arg, (list, tuple, set)):
            for item in arg:
                flatten(item)
        else:
            flattened_list.append(arg)
    flatten(args)
    return flattened_list
