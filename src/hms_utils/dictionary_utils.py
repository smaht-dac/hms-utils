from __future__ import annotations
from copy import deepcopy
import io
import json
import os
from typing import Callable, List, Optional, Tuple, Union


def print_dictionary_tree(data: dict,
                          indent: Optional[int] = None,
                          paths: bool = False,
                          path_separator: str = "/",
                          leafs_first: bool = False,
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
                arrow_indication = arrow_indicator(key_path) if arrow_indicator else ""
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
                          prefix: str = None,
                          key_modifier: Optional[Callable] = None,
                          value_modifier: Optional[Callable] = None,
                          value_annotator: Optional[Callable] = None) -> None:
    if not callable(key_modifier):
        key_modifier = None
    if not callable(value_annotator):
        value_annotator = None
    if not callable(value_modifier):
        value_modifier = None
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


def sort_dictionary(data: dict, leafs_first: bool = False) -> dict:
    if not isinstance(data, dict):
        return data
    sorted_data = {}
    leafs = {key: value for key, value in data.items() if not isinstance(value, dict)}
    nonleafs = {key: value for key, value in data.items() if isinstance(value, dict)}
    for key in sorted(leafs.keys()):
        sorted_data[key] = sort_dictionary(data[key])
    for key in sorted(nonleafs.keys()):
        sorted_data[key] = sort_dictionary(data[key])
    return sorted_data


def load_json_file(file: str, raise_exception: bool = False) -> Optional[dict]:
    if isinstance(file, str) and os.path.isfile(file):
        try:
            with io.open(file, "r") as f:
                return json.load(f)
        except Exception as e:
            import pdb ; pdb.set_trace()  # noqa
            if raise_exception is True:
                raise e
        return None


# This JSON class isa dictionary type which also suport "parent" property for each/every sub-dictionary
# within the main dictionary. Should be able to use EXACTLY like a dicttionary type after creating with
# JSON(dict); including copying and setting properties to any type including either other dictionaies
# or JSON objects. Also has a "root" property on each sub-dictionary referring to the main/root one;
# this just walks up the parent properties to the top (where parent is of course None).
#
class JSON(dict):

    def __init__(self, data: Optional[Union[dict, JSON]] = None, _default: bool = True) -> None:
        if isinstance(data, JSON):
            data = deepcopy(dict(data)) if _default is True else dict(data)
        elif not isinstance(data, dict):
            data = {}
        super().__init__(data)
        self.parent = None
        self._initialize(self) if _default is True else None

    def _initialize(self, parent: JSON) -> None:
        for key in parent:
            child = parent[key]
            if isinstance(child, dict):
                if not isinstance(child, JSON):
                    child = JSON(child, _default=False)
                child.parent = parent
                # child.root = lambda child=child: JSON._root(child)
                super(JSON, parent).__setitem__(key, child)  # bypass override below
                self._initialize(child)

    def __setitem__(self, key, value) -> None:
        if isinstance(value, dict) and id(value.parent) != id(self):
            if isinstance(value, JSON):
                value = deepcopy(value)
            else:
                value = JSON(value)
            value.parent = self
        super().__setitem__(key, value)

    @property
    def root(self) -> Optional[JSON]:
        node = self
        while True:
            if node.parent is None:
                return node
            node = node.parent

    @property
    def context_path(self) -> Optional[str]:
        # FYI we only actually use this (in hms_config) for diagnostic messages.
        context = self
        context_path = []
        context_parent = context.parent
        while context_parent:
            for key in context_parent:
                if context_parent[key] == context:
                    context_path.insert(0, key)
            context = context.parent
            context_parent = context_parent.parent
        return context_path

    def merge(self, secondary: JSON, path_separator: str = "/") -> JSON:
        # Merges the given JSON object into this JSON object; but do not overwrite
        # anything in this JSON object; anything that would otherwise overwrite is ignored.
        merged_config, _, _ = JSON._merge(self, secondary, path_separator=path_separator)
        return merged_config

    @staticmethod
    def _merge(primary: JSON, secondary: JSON, path_separator: str = "/") -> Tuple[dict, list, list]:
        if not (isinstance(primary, dict) or isinstance(secondary, dict)):
            return None, None, None
        merged = deepcopy(primary) ; merged_secrets = [] ; unmerged_secrets = []  # noqa
        def merge(primary: dict, secondary: dict, path: str = "") -> None:  # noqa
            nonlocal unmerged_secrets, path_separator
            for key, value in secondary.items():
                key_path = f"{path}{path_separator}{key}" if path else key
                if key not in primary:
                    primary[key] = secondary[key]
                    merged_secrets.append(key_path)
                elif isinstance(primary[key], dict) and isinstance(secondary[key], dict):
                    merge(primary[key], secondary[key], path=key_path)
                else:
                    unmerged_secrets.append(key_path)
        merge(merged, secondary)
        return merged, merged_secrets, unmerged_secrets

    def __deepcopy__(self, memo) -> JSON:
        return JSON(deepcopy(dict(self), memo))
