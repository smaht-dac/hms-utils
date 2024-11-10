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


def to_flattened_list(*args) -> List[Any]:
    flattened_list = []
    def flatten(arg):  # noqa
        if isinstance(arg, (list, tuple)):
            for item in arg:
                flatten(item)
        else:
            flattened_list.append(arg)
    flatten(args)
    return flattened_list


def get_referenced_uuids(item: Union[dict, List[dict]],
                         ignore_uuids: Optional[List[str]] = None,
                         exclude_uuid: bool = False, uuid_property_name: Optional[str] = None,
                         include_paths: bool = False) -> List[str]:
    """
    Returns a list of uuids which appear as a value anywhere, recursively, within the given
    dictionary or list. But ignores any which are in the given ignore_uuids list. If the
    given exclude_uuid flag is set then ignores values of dictionary properties whose key
    is named "uuid" (or named for the give uuid_property_name). If the given included_paths
    flag is set then also looks for uuid values as a part of slash-separated path values.
    """
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
            elif include_paths is True:
                for component in value.split("/"):
                    if is_uuid(component := component.strip()):
                        uuids.append(component)
        return uuids
    if not isinstance(ignore_uuids, list):
        ignore_uuids = []
    if not (isinstance(uuid_property_name, str) and uuid_property_name):
        uuid_property_name = "uuid"
    if isinstance(item, dict):
        if (exclude_uuid is True) and (uuid := item.get(uuid_property_name)) and (uuid not in ignore_uuids):
            ignore_uuids.append(uuid)
    elif isinstance(item, list):
        for element in item:
            if (exclude_uuid is True) and (uuid := element.get(uuid_property_name)) and (uuid not in ignore_uuids):
                ignore_uuids.append(uuid)
    find_referenced_uuids(item)
    return referenced_uuids


def get_referenced_uuids_from_file(file: str,
                                   ignore_uuids: Optional[List[str]] = None, exclude_uuid: bool = False) -> List[str]:
    try:
        with io.open(file, "r") as f:
            return get_referenced_uuids(json.load(f), ignore_uuids=ignore_uuids, exclude_uuid=exclude_uuid)
    except Exception:
        return []


def get_referenced_uuids_from_files(directory: str,
                                    ignore_uuids: Optional[List[str]] = None, exclude_uuid: bool = False) -> List[str]:
    referenced_uuids = []
    try:
        for file in glob.glob(os.path.join(directory, '*.json')):
            for uuid in get_referenced_uuids_from_file(file, ignore_uuids=ignore_uuids, exclude_uuid=exclude_uuid):
                if uuid not in referenced_uuids:
                    referenced_uuids.append(uuid)
    except Exception:
        pass
    return referenced_uuids


def get_uuids(data: Union[dict, list], uuid_property_name: Optional[str] = None) -> List[str]:
    """
    Returns a list of uuids which appear as a values of properties with a key named "uuid" (or
    name for the given uuid_property_name), recursively, within the given dictionary or list.
    """
    uuids = []
    def get_uuids(data: Union[dict, list]) -> None:  # noqa
        nonlocal uuids, uuid_property_name
        if isinstance(data, list):
            for element in data:
                get_uuids(element)
        elif isinstance(data, dict):
            if uuid := data.get(uuid_property_name):
                if is_uuid(uuid) and (uuid not in uuids):
                    uuids.append(uuid)
            else:
                for value in data.values():
                    if isinstance(value, (dict, list)):
                        get_uuids(value)
    if not (isinstance(uuid_property_name, str) and uuid_property_name):
        uuid_property_name = "uuid"
    get_uuids(data)
    return uuids


def contains_uuid(data: Union[dict, list], uuid: str, uuid_property_name: Optional[str] = None) -> bool:
    """
    Returns true iff the given dictionary or list contains, recursively, a dictionary
    property named "uuid" (or named for the given uuid_property_name) which has a
    value which is equal to the given uuid value; otherwise returns false.
    """
    def contains_uuid(data: Union[dict, list]) -> bool:
        nonlocal uuid
        if isinstance(data, list):
            for element in data:
                if contains_uuid(element):
                    return True
        elif isinstance(data, dict):
            if data.get(uuid_property_name) == uuid:
                return True
            for value in data.values():
                if isinstance(value, (dict, list)):
                    if contains_uuid(value):
                        return True
    if not (isinstance(uuid_property_name, str) and uuid_property_name):
        uuid_property_name = "uuid"
    return contains_uuid(data) if is_uuid(uuid) else False
