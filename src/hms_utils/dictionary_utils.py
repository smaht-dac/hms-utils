from __future__ import annotations
from copy import deepcopy
import glob
import io
import json
import os
from typing import Any, Callable, Iterator, List, Optional, Tuple, Union
from hms_utils.type_utils import is_uuid, to_non_empty_string_list


def print_dictionary_tree(data: dict,
                          indent: Optional[int] = None,
                          paths: bool = False,
                          path_separator: str = "/",
                          key_modifier: Optional[Callable] = None,
                          value_modifier: Optional[Callable] = None,
                          value_annotator: Optional[Callable] = None,
                          arrow_indicator: Optional[Callable] = None,
                          printf: Optional[Callable] = None) -> None:
    """
    Pretty prints the given dictionary. ONLY handles dictionaries
    containing primitive values or other dictionaries recursively.
    """
    if not callable(key_modifier):
        key_modifier = None
    if not callable(value_annotator):
        value_annotator = None
    if not callable(value_modifier):
        value_modifier = None
    if not callable(arrow_indicator):
        arrow_indicator = None
    if not callable(printf):
        printf = print
    output = (lambda value: printf(f"{' ' * indent}{value}")) if isinstance(indent, int) and indent > 0 else printf
    def traverse(data: dict, indent: str = "", first: bool = False, last: bool = True, path: str = ""):  # noqa
        nonlocal output, paths, key_modifier, value_annotator, value_modifier
        space = "    " if not first else "  "
        for index, key in enumerate(keys := list(data.keys())):
            last = (index == len(keys) - 1)
            corner = "▷" if first else ("└──" if last else "├──")
            key_path = f"{path}{path_separator}{key}" if path else key
            if isinstance(value := data[key], dict):
                output(indent + corner + " " + key)
                inner_indent = indent + (space if last else f"{' ' if first else '│'}{space[1:]}")
                traverse(value, indent=inner_indent, last=last, path=key_path)
            else:
                if paths:
                    key = key_path
                key_modification = key_modifier(key_path, key) if key_modifier else key
                value_modification = value_modifier(key_path, value) if value_modifier else value
                value_annotation = value_annotator(key_path) if value_annotator else ""
                arrow_indication = arrow_indicator(key_path, value) if arrow_indicator else ""
                if key_modification:
                    key = key_modification
                if value_modification:
                    value = value_modification
                if arrow_indication:
                    corner = corner[:-1] + arrow_indication
                output(f"{indent}{corner} {key}: {value}{f' {value_annotation}' if value_annotation else ''}")
    traverse(data, first=True)


def print_dictionary_list(data: dict,
                          path_separator: str = "/",
                          prefix: Optional[str] = None,
                          key_modifier: Optional[Callable] = None,
                          value_modifier: Optional[Callable] = None,
                          value_annotator: Optional[Callable] = None) -> None:
    if not callable(key_modifier):
        key_modifier = None
    if not callable(value_annotator):
        value_annotator = None
    if not callable(value_modifier):
        value_modifier = None
    if not isinstance(prefix, str):
        prefix = ""
    def traverse(data: dict, path: str = "") -> None:  # noqa
        nonlocal path_separator, key_modifier, value_annotator, value_modifier
        for key in data:
            key_path = f"{path}{path_separator}{key}" if path else key
            if isinstance(item := data[key], dict):
                traverse(item, path=key_path)
            else:
                value = str(item)
                key_modification = key_modifier(key_path) if key_modifier else key_path
                value_modification = value_modifier(key_path, value) if value_modifier else value
                value_annotation = value_annotator(key_path) if value_annotator else ""
                if key_modification:
                    key = key_modification
                if value_modification:
                    value = value_modification
                print(f"{prefix}{key}: {value}{f' {value_annotation}' if value_annotation else ''}")
    traverse(data)


def delete_paths_from_dictionary(data: dict, paths: List[str], separator: str = "/", copy: bool = True):
    """
    Deletes from the given dictionary the keys/properies specified in the given list of key paths;
    the paths being (by default) a hierarchical-like slash-separated key names, e.g. abc/def/ghi.
    If the copy flag is True this a copy is made of the given dictionary, otherwise it is
    changed in place. In any case returns the resultant dictionary
    """
    if copy is not False:
        data = deepcopy(data)
    def delete(data, keys):  # noqa
        if len(keys) == 1:
            data.pop(keys[0], None)
        else:
            key = keys[0]
            if key in data and isinstance(data[key], dict):
                delete(data[key], keys[1:])
            if not data[key]:
                data.pop(key, None)
    for path in paths:
        keys = path.split('/')
        delete(data, keys)
    return data


def delete_properties_from_dictionaries(data: Union[List[dict], dict], properties: List[str]) -> None:
    """
    Deletes, in place, from the given dictionary or list, recursively, and/all properties
    within dictionaries with a name which is in the list of given properties.
    """
    if properties := to_non_empty_string_list(properties):
        if isinstance(data, list):
            for element in data:
                delete_properties_from_dictionaries(element, properties)
        elif isinstance(data, dict):
            for key in list(data.keys()):
                if key in properties:
                    del data[key]
                else:
                    delete_properties_from_dictionaries(data[key], properties)


def sort_dictionary(data: dict, reverse: bool = False, sensitive: bool = False, lists: bool = False) -> dict:
    """
    Sorts the given dictionary and returns the result; does not change the given dictionary.
    """
    if isinstance(data, list):
        sorted_list = []
        for element in data:
            sorted_list.append(sort_dictionary(element))
        return sorted_list
    if not isinstance(data, dict):
        return data
    sorted_data = {}
    for key in sorted(data.keys(), reverse=reverse is True, key=None if sensitive is True else str.lower):
        sorted_data[key] = sort_dictionary(data[key], reverse=reverse)
    return sorted_data


def load_json_file(file: str, raise_exception: bool = False) -> Optional[dict]:
    if isinstance(file, str) and os.path.isfile(file := os.path.expanduser(file)):
        try:
            with io.open(file, "r") as f:
                return json.load(f)
        except Exception as e:
            if raise_exception is True:
                raise e
        return None


def get_referenced_uuids(item: Union[dict, List[dict]],
                         ignore_uuids: Optional[List[str]] = None,
                         exclude_uuid: bool = False,
                         exclude_properties: Optional[List[str]] = None,
                         uuid_property_name: Optional[str] = None,
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
            for key in item:
                if (not isinstance(exclude_properties, list)) or (key not in exclude_properties):
                    find_referenced_uuids(item[key])
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
            if ((exclude_uuid is True) and isinstance(element, dict) and
                (uuid := element.get(uuid_property_name)) and (uuid not in ignore_uuids)):  # noqa
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


def find_dictionary_item(items: List[dict], property_value: Any, property_name: Optional[str] = None) -> Optional[int]:
    """
    Finds the (first) dictionary in the given list whose "uuid" property (or the property named
    by the given property_name) value matches the given property_value and returns its list index,
    if found; if not found then returns None.
    """
    if isinstance(items, list) and (property_value is not None):
        if not (isinstance(property_name, str) and property_name):
            property_name = "uuid"
        for i in range(len(items)):
            if isinstance(item := items[i], dict):
                if item.get(property_name) == property_value:
                    return i
    return None


# THIS WILL GO AWAY (and using one in dicationary_parented) WHEN hms_config is obsoleted to config/cli.
# This JSON class isa dictionary type which also suport "parent" property for each/every sub-dictionary
# within the main dictionary. Should be able to use EXACTLY like a dicttionary type after creating with
# JSON(dict); including copying and setting properties to any type including either other dictionaies
# or JSON objects. Also has a "root" property on each sub-dictionary referring to the main/root one;
# this just walks up the parent properties to the top (where parent is of course None).
#
class JSON(dict):

    def __init__(self, data: Optional[Union[dict, JSON]] = None,
                 read_value: Optional[Callable] = None,
                 write_value: Optional[Callable] = None,
                 _initializing: bool = False) -> None:
        if isinstance(data, JSON):
            data = deepcopy(dict(data)) if _initializing is not True else dict(data)
        elif not isinstance(data, dict):
            data = {}
        super().__init__(data)
        self._initialized = False
        self._parent = None
        self._write_value = write_value if callable(write_value) else lambda value: value
        self._read_value = read_value if callable(read_value) else lambda value: value

    @property
    def parent(self) -> Optional[JSON]:
        return self._parent

    def items(self) -> Iterator[Tuple[Any, Any]]:
        self._initialize()
        for key, value in super().items():
            if isinstance(value, dict) and (not isinstance(value, JSON)):
                value = JSON(value)
            yield key, value

    def values(self) -> Iterator[Any]:
        self._initialize()
        return super().values()

    @property
    def root(self) -> Optional[JSON]:
        node = self
        while True:
            if node._parent is None:
                return node
            node = node._parent

    @property
    def context_path(self) -> Optional[str]:
        # FYI we only actually use this (in hms_config) for diagnostic messages.
        context = self
        context_path = []
        context_parent = context._parent
        while context_parent:
            for key in context_parent:
                if context_parent[key] == context:
                    context_path.insert(0, key)
            context = context._parent
            context_parent = context_parent._parent
        return context_path

    def sort(self) -> JSON:
        pass

    def merge(self, secondary: JSON, path_separator: str = "/") -> Tuple[dict, List[str], List[str]]:
        # Merges the given secondary JSON object into a COPY of this JSON object; but does not overwrite
        # anything in this JSON object; anything that would otherwise overwrite is ignored. Returns a tuple
        # with (left-to-right) the (new) merged dictionary, a list of paths which were actually merged from
        # the secondary, and a list of paths which were not merged from the secondary, i.e. because they would
        # have overwritten that item in the copy of this JSON object; path delimiter is the given path_separator.
        return JSON._merge(self, secondary, path_separator=path_separator)

    def _initialize(self, parent: Optional[JSON] = None) -> None:
        if self._initialized is False:
            self._initialized = None
            if not parent:
                parent = self
            for key, value in parent.items():
                # value = super(JSON, parent).__getitem__(key)
                if isinstance(value, dict):
                    if not isinstance(value, JSON):
                        value = JSON(value, _initializing=True)
                    value._parent = parent
                    super(JSON, parent).__setitem__(key, value)
                    self._initialize(value)
            self._initialized = True

    def __setitem__(self, key: Any, value: Any) -> None:
        self._initialize()
        if isinstance(value, dict):
            if id(value._parent) != id(self):
                if isinstance(value, JSON):
                    copied_value = deepcopy(value)
                    value = copied_value
                else:
                    value = JSON(value)
                value._parent = self
        else:
            value = self._write_value(value)
        super().__setitem__(key, value)

    def __getitem__(self, key: Any) -> Any:
        self._initialize()
        value = super().__getitem__(key)
        if not isinstance(value, dict):
            value = self._read_value(value)
        return value

    def __delitem__(self, key: Any) -> None:
        self._initialize()
        super().__delitem__(key)

    def __iter__(self) -> Iterator[Any]:
        self._initialize()
        return super().__iter__()

    def __deepcopy__(self, memo) -> JSON:
        return JSON(deepcopy(dict(self), memo))

    @staticmethod
    def _merge(primary: JSON, secondary: JSON, path_separator: str = "/") -> Tuple[dict, List[str], List[str]]:
        # Merges the given secondary JSON object into a COPY of the given primary JSON object; but does not
        # overwrite anything in the primary JSON object; anything that would otherwise overwrite is ignored.
        # Returns a tuple with (in left-right order) the (new) merged dictionary, list of paths which were
        # actually merged from the secondary, and a list of paths which were not merged from the secondary,
        # i.e. because they would have overwritten in the primary; path delimiter is the given path_separator.
        if not (isinstance(primary, dict) or isinstance(secondary, dict)):
            return None, None, None
        merged = deepcopy(primary) ; merged_paths = [] ; unmerged_paths = []  # noqa
        def merge(primary: dict, secondary: dict, path: str = "") -> None:  # noqa
            nonlocal unmerged_paths, path_separator
            for key, value in secondary.items():
                key_path = f"{path}{path_separator}{key}" if path else key
                if key not in primary:
                    primary[key] = secondary[key]
                    merged_paths.append(key_path)
                elif isinstance(primary[key], dict) and isinstance(secondary[key], dict):
                    merge(primary[key], secondary[key], path=key_path)
                else:
                    unmerged_paths.append(key_path)
        merge(merged, secondary)
        return merged, merged_paths, unmerged_paths


def get_property(data: dict, name: str, fallback: Optional[Any] = None) -> Optional[Any]:
    """
    Returns the value of the given property name within the given dictionary, where the given
    property name can be a dot-separated list of property names, which indicate a path into
    nested dictionaries within the given dictionary; returns None if not found.
    """
    if isinstance(data, dict) and isinstance(name, str) and name:
        if keys := name.split("."):
            nkeys = len(keys) ; key_index_max = nkeys - 1  # noqa
            for key_index in range(nkeys):
                key = keys[key_index]
                if (value := data.get(key, None)) is None:
                    break
                elif key_index == key_index_max:
                    return value
                elif not isinstance(value, dict):
                    break
                else:
                    data = value
    return fallback
