from __future__ import annotations
from copy import deepcopy
from typing import Any, Callable, List, Optional, Tuple, Union
from hms_utils.dictionary_utils import sort_dictionary
from hms_utils.path_utils import unpack_path
from hms_utils.type_utils import is_primitive_type


# This JSON class isa dictionary type which also suport "parent" property for each/every sub-dictionary
# within the main dictionary. Should be able to use EXACTLY like a dicttionary type after creating with
# JSON(dict); including copying and setting properties to any type including either other dictionaies
# or JSON objects. Also has a "root" property on each sub-dictionary referring to the main/root one;
# this just walks up the parent properties to the top (where parent is of course None).
#
class JSON(dict):

    _PATH_SEPARATOR = "/"

    def __init__(self, data: Optional[Union[dict, JSON]] = None, rvalue: Optional[Callable] = None) -> None:
        if isinstance(data, JSON):
            data = dict(data)
        elif not isinstance(data, dict):
            data = {}
        super().__init__(data)
        self._initialize(rvalue)

    def _initialize(self, rvalue: Optional[Callable] = None) -> None:
        if not callable(rvalue):
            rvalue = None
        self._parent = None
        for key in self:
            value = super(JSON, self).__getitem__(key)
            if isinstance(value, dict):
                value = JSON(value, rvalue=rvalue)
                value._parent = self
                super(JSON, self).__setitem__(key, value)
            elif isinstance(value, list):
                value_list = []
                for element in value:
                    if isinstance(element, dict):
                        value_list.append(JSON(element, rvalue=rvalue))
                    else:
                        value_list.append(element)
                super().__setitem__(key, value_list)
            elif rvalue and is_primitive_type(value):
                super().__setitem__(key, rvalue(value))

    @property
    def parent(self) -> Optional[JSON]:
        return self._parent

    @property
    def root(self) -> Optional[JSON]:
        node = self
        while True:
            if node._parent is None:
                return node
            node = node._parent

    def context_path(self, path_separator: Optional[Union[str, bool]] = None,
                     path_rooted: bool = False, path_suffix: Optional[str] = None) -> Union[List[str], str]:
        # FYI we only actually use this in hms_config for diagnostic messages.
        context = self
        context_path = []
        context_parent = context._parent
        while context_parent:
            for key in context_parent:
                if context_parent[key] == context:
                    context_path.insert(0, key)
            context = context._parent
            context_parent = context_parent._parent
        if isinstance(path_suffix, str) and path_suffix:
            context_path.append(path_suffix)
        if path_separator is True:
            path_separator = JSON._PATH_SEPARATOR
        elif (path_separator is False) or (not isinstance(path_separator, str)):
            path_separator = None
        if path_separator:
            if path_rooted is True:
                return path_separator + path_separator.join(context_path)
            return path_separator.join(context_path)
        return context_path

    @property
    def path(self) -> str:
        return self.context_path(path_separator=True, path_rooted=id(self) == id(self.root))

    def sorted(self, reverse: bool = False) -> JSON:
        return JSON(sort_dictionary(self.root, reverse=reverse)).lookup(self.path)

    def merge(self, secondary: JSON, path_separator: Optional[str] = None) -> Tuple[JSON, List[str], List[str]]:
        # Merges the given secondary JSON object into a COPY of this JSON object; but does not overwrite
        # anything in this JSON object; anything that would otherwise overwrite is ignored. Returns a tuple
        # with (left-to-right) the (new) merged dictionary, a list of paths which were actually merged from the
        # secondary, and a list of paths which were not merged from the secondary, i.e. because they would have
        # overwritten that item in the copy of this JSON object; path delimiter is the given path_separator.
        def merge(primary: JSON, secondary: JSON) -> Tuple[JSON, List[str], List[str]]:
            nonlocal path_separator
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
            return JSON(merged), merged_paths, unmerged_paths
        if (not isinstance(path_separator, str)) or (not path_separator):
            path_separator = JSON._PATH_SEPARATOR
        return merge(self, secondary)

    def lookup(data, path: str, path_separator: Optional[str] = None) -> Optional[Union[Any, JSON]]:
        if (not isinstance(path, str)) or (not path):
            return None, data
        if (not isinstance(path_separator, str)) or (not path_separator):
            path_separator = JSON._PATH_SEPARATOR
        if not (path_components := unpack_path(path, path_separator=path_separator)):
            return None, data
        if path_components[0] == path_separator:
            if not (path_components := path_components[1:]):
                return data
            context = data.root
        else:
            context = data
        value = None
        for path_component_index, path_component in enumerate(path_components):
            if (value := context.get(path_component)) is None:
                break
            if isinstance(value, JSON):
                context = value
            elif path_component_index < (len(path_components) - 1):
                value = None
                break
        return value

    def duplicate(self, rvalue: Optional[Callable] = None) -> JSON:
        return JSON(self.root, rvalue=rvalue).lookup(self.path)

    def __setitem__(self, key: Any, value: Any) -> None:
        if isinstance(value, dict):
            if not isinstance(value, JSON):
                value = JSON(value)
            if id(value._parent) != id(self):
                if isinstance(value, JSON):
                    copied_value = deepcopy(value)
                    value = copied_value
                else:
                    value = JSON(value)
                value._parent = self
        super().__setitem__(key, value)

    def __deepcopy__(self, memo) -> JSON:
        return JSON(deepcopy(dict(self), memo))


DictionaryParented = JSON
