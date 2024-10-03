from __future__ import annotations
from copy import deepcopy
from typing import Any, Callable, Iterator, List, Optional, Tuple, Union
from hms_utils.dictionary_utils import sort_dictionary
from hms_utils.misc_utils import is_primitive_type


# This JSON class isa dictionary type which also suport "parent" property for each/every sub-dictionary
# within the main dictionary. Should be able to use EXACTLY like a dicttionary type after creating with
# JSON(dict); including copying and setting properties to any type including either other dictionaies
# or JSON objects. Also has a "root" property on each sub-dictionary referring to the main/root one;
# this just walks up the parent properties to the top (where parent is of course None).
#
class JSON(dict):

    def __init__(self, data: Optional[Union[dict, JSON]] = None, read_value: Optional[Callable] = None) -> None:
        if isinstance(data, JSON):
            data = data._asdict()
        elif not isinstance(data, dict):
            data = {}
        super().__init__(data)
        self._initialized = False
        self._parent = None
        self._rvalue = read_value if callable(read_value) else None

    def _initialize(self, parent: Optional[JSON] = None) -> None:
        if self._initialized is False:
            self._initialized = None
            if not parent:
                parent = self
            for key in parent:
                value = super(JSON, parent).__getitem__(key)
                if isinstance(value, dict):
                    if not isinstance(value, JSON):
                        value = JSON(value)
                    value._parent = parent
                    super(JSON, parent).__setitem__(key, value)
                    self._initialize(value)
            self._initialized = True

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

    def path(self, path_separator: Optional[Union[str, bool]] = None, path_rooted: bool = False) -> Optional[str]:
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
        if path_separator is True:
            path_separator = "/"
        elif (path_separator is False) or (not isinstance(path_separator, str)):
            path_separator = None
        if path_separator:
            if path_rooted is True:
                return path_separator + path_separator.join(context_path)
            return path_separator.join(context_path)
        return context_path

    @property
    def context_path(self) -> Optional[str]:
        return self.path(path_separator=False, path_rooted=False)

    def get(self, key: Any, default: Any = None) -> Any:
        if key not in self:
            return default
        return self[key]

    def __getitem__(self, key: Any) -> Any:
        self._initialize()
        value = super().__getitem__(key)
        if self._rvalue and (not isinstance(value, dict)):
            value = self._rvalue(value)
        return value

    def items(self) -> Iterator[Tuple[Any, Any]]:
        self._initialize()
        for key, value in super().items():
            if isinstance(value, dict) and (not isinstance(value, JSON)):
                value = JSON(value)
            yield key, value

    def values(self) -> Iterator[Any]:
        self._initialize()
        return super().values()

    def __setitem__(self, key: Any, value: Any) -> None:
        self._initialize()
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

    def __iter__(self) -> Iterator[Any]:
        self._initialize()
        return super().__iter__()

    def __deepcopy__(self, memo) -> JSON:
        return JSON(deepcopy(dict(self), memo))

    def sorted(self, reverse: bool = False, leafs_first: bool = False) -> JSON:
        return JSON(sort_dictionary(self, reverse=reverse, leafs_first=leafs_first))

    def merge(self, secondary: JSON, path_separator: str = "/") -> Tuple[dict, List[str], List[str]]:
        # Merges the given secondary JSON object into a COPY of this JSON object; but does not overwrite
        # anything in this JSON object; anything that would otherwise overwrite is ignored. Returns a tuple
        # with (left-to-right) the (new) merged dictionary, a list of paths which were actually merged from the
        # secondary, and a list of paths which were not merged from the secondary, i.e. because they would have
        # overwritten that item in the copy of this JSON object; path delimiter is the given path_separator.
        return JSON._merge(self, secondary, path_separator=path_separator)

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

    def _asdict(self, rvalue: Union[bool, Callable] = False) -> dict:
        if rvalue is True:
            rvalue = self._rvalue
        elif (rvalue is False) or (not callable(rvalue)):
            rvalue = lambda value: value  # noqa
        def asdict(value) -> str:  # noqa
            if isinstance(value, dict):
                return {key: asdict(value) for key, value in value.items()}
            elif isinstance(value, list):
                return [asdict(element) for element in value]
            elif is_primitive_type(value):
                return rvalue(value)
            return value
        return asdict(self)

    def __str__(self) -> str:
        if not self._rvalue:
            return super().__str__()
        return str(self._asdict())

    def __repr__(self) -> str:
        if not self._rvalue:
            return super().__repr__()
        return repr(self._asdict())


ParentedJSON = JSON
