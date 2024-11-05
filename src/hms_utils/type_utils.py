import glob
import io
import json
import os
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


def get_referenced_uuids(item: Union[dict, List[dict]],
                         ignore_uuids: Optional[List[str]] = None, ignore_uuid: bool = False) -> List[str]:
    referenced_uuids = []
    def find_referenced_uuids(item: Any) -> None:  # noqa
        nonlocal referenced_uuids, ignore_uuids
        if isinstance(item, dict):
            for value in item.values():
                find_referenced_uuids(value)
        elif isinstance(item, (list, tuple)):
            for element in item:
                find_referenced_uuids(element)
        elif uuids := get_uuids_from_value(item):
            for uuid in uuids:
                if (uuid not in ignore_uuids) and (uuid not in referenced_uuids):
                    referenced_uuids.append(uuid)
    def get_uuids_from_value(value: str) -> List[str]:  # noqa
        uuids = []
        if isinstance(value, str):
            if is_uuid(value):
                uuids.append(value)
            else:
                for component in value.split("/"):
                    if is_uuid(component := component.strip()):
                        uuids.append(component)
        return uuids
    if not isinstance(ignore_uuids, list):
        ignore_uuids = []
    if isinstance(item, dict):
        if (ignore_uuid is True) and (uuid := item.get("uuid")) and (uuid not in ignore_uuids):
            ignore_uuids.append(uuid)
    elif isinstance(item, list):
        for item in item:
            if (ignore_uuid is True) and (uuid := item.get("uuid")) and (uuid not in ignore_uuids):
                ignore_uuids.append(uuid)
    find_referenced_uuids(item)
    return referenced_uuids


def get_referenced_uuids_from_file(file: str,
                                   ignore_uuids: Optional[List[str]] = None, ignore_uuid: bool = False) -> List[str]:
    try:
        with io.open(file, "r") as f:
            return get_referenced_uuids(json.load(f), ignore_uuids=ignore_uuids, ignore_uuid=ignore_uuid)
    except Exception:
        return []


def get_referenced_uuids_from_files(directory: str,
                                    ignore_uuids: Optional[List[str]] = None, ignore_uuid: bool = False) -> List[str]:
    referenced_uuids = []
    try:
        for file in glob.glob(os.path.join(directory, '*.json')):
            for uuid in get_referenced_uuids_from_file(file, ignore_uuids=ignore_uuids, ignore_uuid=ignore_uuid):
                if uuid not in referenced_uuids:
                    referenced_uuids.append(uuid)
    except Exception:
        pass
    return referenced_uuids
