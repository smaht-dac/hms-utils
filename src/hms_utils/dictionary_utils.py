from __future__ import annotations
from collections import defaultdict, deque
from copy import deepcopy
import glob
import io
import json
import os
from typing import Any, Callable, Iterator, List, Optional, Tuple, Union
from hms_utils.type_utils import is_uuid, to_non_empty_string_list


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
    def sorted_key(key: Any) -> str:  # noqa
        if not isinstance(key, str):
            key = str(key)
        return key.lower() if (sensitive is True) else key
    for key in sorted(data.keys(), reverse=reverse is True, key=sorted_key):
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
                if (value := data.get(keys[key_index], None)) is not None:
                    if key_index == key_index_max:
                        return value
                    elif isinstance(value, dict):
                        data = value
                        continue
                break
    return fallback


def get_properties(data: dict, name: str, fallback: Optional[Any] = None, sort: bool = False) -> List[Any]:
    """
    Returns the values of the given property name within the given dictionary as a list, where the
    given property name can be a dot-separated list of property names, which indicate a path into
    nested dictionaries within the given dictionary; and - where if any of the elements within
    the path are lists then we iterate through each, collecting the values for each and including
    each within the list of returned values.
    """
    if isinstance(data, dict) and isinstance(name, str) and name:
        if keys := name.split("."):
            nkeys = len(keys) ; key_index_max = nkeys - 1  # noqa
            for key_index in range(nkeys):
                if (value := data.get(keys[key_index], None)) is not None:
                    if key_index == key_index_max:
                        return [value]
                    elif isinstance(value, dict):
                        data = value
                        continue
                    elif isinstance(value, list) and value and ((sub_key_index := key_index + 1) < nkeys):
                        sub_key = ".".join(keys[sub_key_index:])
                        values = []
                        for element in value:
                            if isinstance(element_value := get_properties(element, sub_key), list):
                                for element_value_item in element_value:
                                    if (element_value_item is not None) and (element_value_item not in values):
                                        values.append(element_value_item)
                            elif (element_value is not None) and (element_value not in values):
                                values.append(element_value)
                        return sorted(values) if (sort is True) else values
                break
    return fallback if isinstance(fallback, list) else ([] if fallback is None else [fallback])


def select_items(items: List[dict], predicate: Callable) -> List[dict]:
    if not (isinstance(items, list) and items):
        return []
    return [item for item in items if predicate(item)]


def group_items_by(items: list[dict], grouping: str,
                   sort: bool = False,
                   noitems: bool = False,
                   omit_unique_items_count: bool = False,
                   map_grouping_value: Optional[Callable] = None,
                   prefix_grouping_value: bool = False,
                   identifying_property: Optional[str] = "uuid",
                   raw: bool = False) -> dict:
    if not (isinstance(items, list) and items and isinstance(grouping, str) and (grouping := grouping.strip())):
        return {}
    if not callable(map_grouping_value):
        map_grouping_value = None
    if not (isinstance(identifying_property, str) and (identifying_property := identifying_property.strip())):
        identifying_property = None
    # Initialize results with first None element to make sure items which are not
    # part of a group are listed first; delete later of no such (ungrouped) items;
    # though if sort is True then this is irrelevant.
    non_unique_item_count = 0
    results = {None: 0 if noitems is True else []}
    for item in items:
        if identifying_property and ((identifying_value := item.get(identifying_property)) is not None):
            item_identity = identifying_value
        else:
            item_identity = item
        if grouping_values := get_properties(item, grouping):
            for grouping_value in grouping_values:
                # This prefixing with the grouping name was added later when we realized it is useful to have,
                # for each individual item grouped, the name of the grouping for which it is from.
                if map_grouping_value:
                    if (grouping_value := map_grouping_value(grouping, grouping_value)) is None:
                        continue
                if prefix_grouping_value is True:
                    grouping_value = f"{grouping}:{grouping_value}"
                if noitems is True:
                    if results.get(grouping_value) is None:
                        results[grouping_value] = 0
                    results[grouping_value] += 1
                else:
                    if results.get(grouping_value) is None:
                        results[grouping_value] = []
                    results[grouping_value].append(item_identity)
                non_unique_item_count += 1
        elif noitems is True:
            results[None] += 1
            non_unique_item_count += 1
        else:
            results[None].append(item_identity)
            non_unique_item_count += 1
    if not results[None]:
        del results[None]
    if sort is True:
        # Currently sort means to sort the groups in descending order of the
        # number of items in each group list; and secondarily by the group value.
        if noitems is True:
            results = dict(sorted(results.items(), key=lambda item: (-item[1], item[0] is None, item[0] or "")))
        else:
            results = dict(sorted(results.items(), key=lambda item: (-len(item[1]), item[0] is None, item[0] or "")))
    if (raw is True) or (not results):
        return results
    results = {
        "group": grouping,
        "item_count": non_unique_item_count,
        "unique_item_count": len(items),
        "group_count": len(results),
        "group_items": results
    }
    if omit_unique_items_count is True:
        del results["unique_item_count"]
    return results


def group_items_by_groupings(items: List[dict], groupings: List[str],
                             sort: bool = False,
                             noitems: bool = False,
                             omit_unique_items_count: bool = False,
                             map_grouping_value: Optional[Callable] = None,
                             prefix_grouping_value: bool = False,
                             identifying_property: Optional[str] = "uuid") -> dict:
    if not (isinstance(items, list) and items):
        return {}
    if isinstance(groupings, str) and groupings:
        groupings = [groupings]
    elif not (isinstance(groupings, list) and groupings):
        return {}
    if not (isinstance(identifying_property, str) and (identifying_property := identifying_property.strip())):
        identifying_property = None
    if not (grouped_items := group_items_by(items, groupings[0], sort=sort,
                                            omit_unique_items_count=omit_unique_items_count,
                                            map_grouping_value=map_grouping_value,
                                            prefix_grouping_value=prefix_grouping_value,
                                            identifying_property=identifying_property)):
        return {}
    def sub_group_items_by(group_items: dict, grouping: str) -> None:  # noqa
        nonlocal items, sort, omit_unique_items_count, map_grouping_value, identifying_property
        for grouped_item_key in group_items:
            if isinstance(group_items[grouped_item_key], list):
                sub_items = select_items(
                    items, lambda item: item.get(identifying_property) in group_items[grouped_item_key])
                group_items[grouped_item_key] = group_items_by(
                    sub_items, grouping, sort=sort,
                    omit_unique_items_count=omit_unique_items_count,
                    map_grouping_value=map_grouping_value,
                    prefix_grouping_value=prefix_grouping_value,
                    identifying_property=identifying_property)
            elif isinstance(group_items[grouped_item_key], dict):
                sub_group_items_by(group_items[grouped_item_key]["group_items"], grouping)
    for grouping in groupings[1:]:
        if isinstance(grouping, str) and (grouping := grouping.strip()):
            sub_group_items_by(grouped_items["group_items"], grouping)
    if noitems is True:
        def change_group_items_list_to_group_items_count(grouped_items: dict) -> None:
            if isinstance(group_items := grouped_items.get("group_items"), dict):
                for group_item_key in group_items:
                    if isinstance(group_items[group_item_key], dict):
                        change_group_items_list_to_group_items_count(group_items[group_item_key])
                    elif isinstance(group_items[group_item_key], list):
                        group_items[group_item_key] = len(group_items[group_item_key])
        change_group_items_list_to_group_items_count(grouped_items)
    return grouped_items


def compare_dictionaries_ordered(a: dict, b: dict) -> bool:
    # CAVEAT: Written by ChatGPT and used without almost no review (just testing)!
    def compare_lists_ordered(a: list, b: list):
        if len(a) != len(b):
            return False
        for aitem, bitem in zip(a, b):
            if isinstance(aitem, dict) and isinstance(bitem, dict):
                if not compare_dictionaries_ordered(aitem, bitem):
                    return False
            elif isinstance(aitem, list) and isinstance(bitem, list):
                if not compare_lists_ordered(aitem, bitem):
                    return False
            elif aitem != bitem:
                return False
        return True
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    if list(a.keys()) != list(b.keys()):
        return False
    for key in a:
        avalue = a[key]
        bvalue = b[key]
        if isinstance(avalue, dict) and isinstance(bvalue, dict):
            if not compare_dictionaries_ordered(avalue, bvalue):
                return False
        elif isinstance(avalue, list) and isinstance(bvalue, list):
            if not compare_lists_ordered(avalue, bvalue):
                return False
        elif avalue != bvalue:
            return False
    return True


def order_dictionary_by_dependencies(items: List[dict],
                                     dependencies: Union[List[str], str, Callable],
                                     identifying_property_name: str = "uuid") -> List[dict]:
    """
    Orders the given list of items (dictionaries) so that each item appears after its dependencies
    as defined by the given dependencies argument, where this can be a property name or a list of
    property names of identifying values, or a callable which returns the identifying values for
    a given item. There must be a single identifying value for each record whose property name
    is specified by the given identifying_property_name argument, or is "uuid" if none.
    Returns the ordered list of items; does NOT make changes in place.
    CAVEAT: This function was adapted from ChatGPT generated code.
    """
    if not isinstance(items, list):
        return []
    if not (isinstance(identifying_property_name, str) and identifying_property_name):
        identifying_property_name = "uuid"
    if not callable(dependencies):
        dependent_property_names = []
        if isinstance(dependencies, list):
            for dependency in dependencies:
                if isinstance(dependency, str) and dependency:
                    dependent_property_names.append(dependency)
        elif isinstance(dependencies, str) and dependencies:
            dependent_property_names = [dependencies]
        if not dependent_property_names:
            return items
        def get_dependencies(item: dict) -> List[str]:  # noqa
            nonlocal dependent_property_names
            dependency_values = []
            for dependent_property_name in dependent_property_names:
                if (dependency_value := item.get(dependent_property_name)) is not None:
                    if isinstance(dependency_value_list := dependency_value, list):
                        for dependency_value in dependency_value_list:
                            if dependency_value is not None:
                                dependency_values.append(dependency_value)
                    else:
                        dependency_values.append(dependency_value)
            return dependency_values
        dependencies = get_dependencies

    # Create a map from identifying-value to item.
    identifying_value_to_item_map = {item[identifying_property_name]: item for item in items}

    # Create adjacency list and in-degree count for topological sort.
    adjacency_list = defaultdict(list)
    in_degree = defaultdict(int)

    # Build graph.
    for item in items:
        identifying_value = item[identifying_property_name]
        if isinstance(dependency_values := dependencies(item), list):
            for dependency_value in dependency_values:
                if dependency_value is not None:
                    adjacency_list[dependency_value].append(identifying_value)
                    in_degree[identifying_value] += 1

    # Topological sort.
    sorted_items = []
    zero_in_degree = deque([identifying_value for identifying_value in identifying_value_to_item_map
                            if in_degree[identifying_value] == 0])
    while zero_in_degree:
        current_identifying_value = zero_in_degree.popleft()
        sorted_items.append(identifying_value_to_item_map[current_identifying_value])
        for dependent_value in adjacency_list[current_identifying_value]:
            in_degree[dependent_value] -= 1
            if in_degree[dependent_value] == 0:
                zero_in_degree.append(dependent_value)

    # Check for cycles (unsatisfied dependencies).
    if len(sorted_items) != len(items):
        raise ValueError("The input contains cyclic dependencies and cannot be ordered.")

    return sorted_items


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
