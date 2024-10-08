from __future__ import annotations
from copy import deepcopy
from typing import Any, Callable, Iterator, List, Optional, Tuple, Union
from hms_utils.chars import chars
from hms_utils.dictionary_print_utils import print_dictionary_tree
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
            if rvalue_from_data := data._rvalue:
                if callable(rvalue_from_arg := rvalue):
                    rvalue = lambda value: rvalue_from_arg(rvalue_from_data(value))  # noqa
                else:
                    rvalue = rvalue_from_data
            data = data.asdict(rvalue=False)
        elif not isinstance(data, dict):
            data = {}
        super().__init__(data)
        self._initialized = False
        self._parent = None
        self._rvalue = rvalue if callable(rvalue) else None

    def _initialize(self, parent: Optional[JSON] = None) -> None:
        if self._initialized is False:
            self._initialized = None
            if not parent:
                parent = self
            for key in parent:
                value = super(JSON, parent).__getitem__(key)
                if isinstance(value, dict):
                    if not isinstance(value, JSON):
                        value = JSON(value, rvalue=self._rvalue)
                    value._parent = parent
                    super(JSON, parent).__setitem__(key, value)
                    self._initialize(value)
                elif isinstance(value, list) and False:
                    # Just for completeness do any dictionaries nested within lists.
                    parent_key_value = []
                    for element in value:
                        if isinstance(element, dict) and (not isinstance(element, JSON)):
                            parent_key_value.append(JSON(element))
                        else:
                            parent_key_value.append(element)
                    super().__setitem__(key, parent_key_value)
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

    def get(self, key: Any, default: Any = None) -> Any:
        if key not in self:
            return default
        return self[key]

    def __getitem__(self, key: Any) -> Any:
        self._initialize()
        value = super().__getitem__(key)
        if self._rvalue and is_primitive_type(value):
            value = self._rvalue(value)
        return value

    def items(self) -> Iterator[Tuple[Any, Any]]:
        self._initialize()
        for key, value in super().items():
            if isinstance(value, dict) and (not isinstance(value, JSON)):
                value = JSON(value)
            if self._rvalue and is_primitive_type(value):
                value = self._rvalue(value)
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

    def merge(self, secondary: JSON, path_separator: Optional[str] = None) -> Tuple[dict, List[str], List[str]]:
        # Merges the given secondary JSON object into a COPY of this JSON object; but does not overwrite
        # anything in this JSON object; anything that would otherwise overwrite is ignored. Returns a tuple
        # with (left-to-right) the (new) merged dictionary, a list of paths which were actually merged from the
        # secondary, and a list of paths which were not merged from the secondary, i.e. because they would have
        # overwritten that item in the copy of this JSON object; path delimiter is the given path_separator.
        if (not isinstance(path_separator, str)) or (not path_separator):
            path_separator = JSON._PATH_SEPARATOR
        return JSON._merge(self, secondary, path_separator=path_separator)

    @staticmethod
    def _merge(primary: JSON, secondary: JSON,
               path_separator: Optional[str] = None) -> Tuple[dict, List[str], List[str]]:
        # Merges the given secondary JSON object into a COPY of the given primary JSON object; but does not
        # overwrite anything in the primary JSON object; anything that would otherwise overwrite is ignored.
        # Returns a tuple with (in left-right order) the (new) merged dictionary, list of paths which were
        # actually merged from the secondary, and a list of paths which were not merged from the secondary,
        # i.e. because they would have overwritten in the primary; path delimiter is the given path_separator.
        if not (isinstance(primary, dict) or isinstance(secondary, dict)):
            return None, None, None
        if (not isinstance(path_separator, str)) or (not path_separator):
            path_separator = JSON._PATH_SEPARATOR
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

    def asdict(self, rvalue: Union[bool, Callable] = True) -> dict:
        if rvalue_from_self := self._rvalue:
            if callable(rvalue_from_arg := rvalue):
                rvalue = lambda value: rvalue_from_arg(rvalue_from_self(value))  # noqa
            elif rvalue_from_arg is False:
                rvalue = lambda value: value  # noqa
            else:
                rvalue = rvalue_from_self
        elif callable(rvalue_from_arg := rvalue):
            rvalue = rvalue_from_arg
        else:
            rvalue = lambda value: value  # noqa
        def asdict(value) -> str:  # noqa
            nonlocal rvalue
            if isinstance(value, dict):
                return {key: asdict(value) for key, value in value.items()}
            elif isinstance(value, list) and False:
                return [asdict(element) for element in value]
            elif is_primitive_type(value):
                return rvalue(value)
            return value
        return asdict(self)

    def __str__(self) -> str:
        if not self._rvalue:
            return super().__str__()
        return str(self.asdict())

    def _dump_for_testing(self, verbose: bool = False, check: bool = False) -> None:
        def root_indicator() -> str:
            nonlocal self
            indicator = f"\b\b{chars.rarrow} root {chars.dot} id: {id(self)}"
            if self.parent:
                indicator += f" {chars.dot} parent: {id(self.parent)}"
            return indicator
        def parent_annotator(parent: JSON) -> str:  # noqa
            nonlocal self, check
            annotation = (f" {chars.dot} id: {id(parent)} {chars.dot_hollow}"
                          f"{f' parent: {id(parent.parent)}' if parent.parent else ''}")
            if check is True:
                path = parent.context_path(path_separator=True, path_rooted=True)
                checked_value, _ = self._lookup(path)
                annotation += f" {chars.check if id(checked_value) == id(parent) else chars.xmark}"
            return annotation
        def value_annotator(parent: JSON, key: Any, value: Any) -> str:  # noqa
            nonlocal self, check
            annotation = f" {chars.dot} parent: {id(parent)}"
            path = None
            if (verbose is True) or (check is True):
                if isinstance(parent, JSON):
                    path = parent.context_path(path_separator=True, path_rooted=True, path_suffix=key)
            if (verbose is True) and path:
                pass
                annotation += f" {chars.rarrow_hollow} {path}"
            if (check is True) and path:
                checked_value, _ = parent._lookup(path)
                annotation += f" {chars.check if id(checked_value) == id(value) else chars.xmark}"
            return annotation
        print_dictionary_tree(self,
                              root_indicator=root_indicator,
                              parent_annotator=parent_annotator,
                              value_annotator=value_annotator, indent=2)

    def _lookup(self, path: str, path_separator: Optional[str] = None) -> Tuple[Optional[Union[Any, JSON]], JSON]:
        if (not isinstance(path, str)) or (not path):
            return None, self
        if (not isinstance(path_separator, str)) or (not path_separator):
            path_separator = JSON._PATH_SEPARATOR
        if not (path_components := unpack_path(path, path_separator=path_separator)):
            return None, self
        if path_components[0] == path_separator:
            path_components = path_components[1:]
            context = self.root
        else:
            context = self
        value = None
        for path_component_index, path_component in enumerate(path_components):
            if (value := context.get(path_component)) is None:
                break
            if isinstance(value, JSON):
                context = value
            elif path_component_index < (len(path_components) - 1):
                value = None
                break
        return value, context


DictionaryParented = JSON
