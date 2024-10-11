from __future__ import annotations
import os
import re
import sys
from typing import Any, Callable, List, Optional, Tuple, Union
from hms_utils.path_utils import repack_path, unpack_path
from hms_utils.dictionary_utils import load_json_file
from hms_utils.dictionary_parented import DictionaryParented as JSON
from hms_utils.type_utils import is_primitive_type


class ConfigBasic:

    _PATH_SEPARATOR = "/"
    _PATH_COMPONENT_CURRENT = "."
    _PATH_COMPONENT_PARENT = ".."
    _PATH_COMPONENT_ROOT = _PATH_SEPARATOR
    _MACRO_START = "${"
    _MACRO_END = "}"
    _MACRO_PATTERN = re.compile(r"\$\{([^}]+)\}")
    _MACRO_HIDE_START = "@@@@@@@__macro_hide_start_["
    _MACRO_HIDE_END = "]__macro_hide_end_@@@@@@@"
    _MACRO_PATTERN = re.compile(r"\$\{([^}]+)\}")
    _TRICKY_FIX = True

    def __init__(self, config: Union[dict, str],
                 name: Optional[str] = None,
                 path_separator: Optional[str] = None,
                 custom_macro_lookup: Optional[Callable] = None,
                 raise_exception: bool = False) -> None:

        if not (isinstance(path_separator, str) and (path_separator := path_separator.strip())):
            path_separator = ConfigBasic._PATH_SEPARATOR
        if isinstance(config, str):
            config = load_json_file(config)
        elif isinstance(config, JSON) or (not isinstance(config, dict)):
            raise Exception("Must create Config object with dictionary or file path.")
        self._json = self._create_json(config)
        self._name = name if isinstance(name, str) and name else None
        self._includes = None
        self._path_separator = path_separator
        self._custom_macro_lookup = custom_macro_lookup if callable(custom_macro_lookup) else None
        self._ignore_missing_macros = True
        self._ignore_circular_macros = True
        self._ignore_structured_macros = True
        self._warnings = []
        self._raise_exception = raise_exception is True
        self._merged = []

    def _create_json(self, data: dict) -> JSON:
        return JSON(data)

    def data(self, sorted: bool = True) -> JSON:
        return self._json.sorted() if sorted is True else self._json

    @property
    def json(self) -> JSON:
        return self._json

    @property
    def name(self) -> Optional[str]:
        return self._name

    def merge(self, data: Union[Union[dict, ConfigBasic],
                                List[Union[dict, ConfigBasic]]]) -> Tuple[List[str], List[str]]:
        merged_paths = [] ; unmerged_paths = []  # noqa
        if isinstance(data, (dict, ConfigBasic)):
            data = [data]
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and (not isinstance(item, JSON)):
                    item = JSON(item)
                elif isinstance(item, ConfigBasic):
                    if merged_name := item.name:
                        self._merged.append(merged_name)
                    item = item._json
                if isinstance(item, JSON):
                    self._json, item_merged_paths, item_unmerged_paths = (
                        self._json.merge(item, path_separator=self._path_separator))
                    merged_paths.extend(item_merged_paths)
                    unmerged_paths.extend(item_unmerged_paths)
        return merged_paths, unmerged_paths

    def include(self, data: Union[List[Union[dict, ConfigBasic]], Union[dict, ConfigBasic]]) -> None:
        if isinstance(data, (dict, ConfigBasic)):
            data = [data]
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and (not isinstance(item, JSON)):
                    item = ConfigBasic(item)
                if isinstance(item, ConfigBasic):
                    if self._includes is None:
                        self._includes = []
                    self._includes.append(item)
                    if item.secrets:
                        self._secrets = True

    def lookup(self, path: str,
               context: Optional[JSON] = None,
               noexpand: bool = False,
               inherit_simple: bool = False,
               inherit_none: bool = False, **kwargs) -> Optional[Union[Any, JSON]]:
        context = context if isinstance(context, JSON) else self._json
        value, context = self._lookup(path, context=context, inherit_simple=inherit_simple, inherit_none=inherit_none)
        value = value if ((value is None) or (noexpand is True)) else self.expand_macros(value, context)
        if (value is None) and self._includes:
            for includes in self._includes:
                if (value := includes.lookup(path, noexpand=noexpand,
                                             inherit_simple=inherit_simple,
                                             inherit_none=inherit_none, **kwargs)) is not None:
                    break
        return value

    def _lookup(self, path: str, context: Optional[JSON] = None,
                inherit_simple: bool = False, inherit_none: bool = False) -> Tuple[Optional[Union[Any, JSON]], JSON]:

        def lookup_path_components(path_components: List[str], context: JSON) -> Tuple[Optional[Any], JSON]:
            value = None
            for path_component_index, path_component in enumerate(path_components):
                if (value := context.get(path_component)) is None:
                    break
                if isinstance(value, JSON):
                    # Found a JSON in the path so recurse down to it.
                    context = value
                elif path_component_index < (len(path_components) - 1):
                    # Found a terminal (non-JSON) in the path but it is not the last component.
                    value = None
                    break
            return value, context, path_component_index

        secondary_contexts = []
        if context is None:
            context = self._json
        elif isinstance(context, list) and context:
            secondary_contexts = context[1:]
            context = context[0]
        elif not isinstance(context, JSON):
            context = self._json

        value = None

        if not (path_components := self.unpack_path(path)):
            return value, context
        if path_rooted := (path_components[0] == ConfigBasic._PATH_COMPONENT_ROOT):
            if not (path_components := path_components[1:]):
                return value, context
            context = context.root

        value, context, path_component_index = lookup_path_components(path_components, context)
        if (value is None) and secondary_contexts:
            for secondary_context in secondary_contexts:
                value, _, _ = lookup_path_components(path_components, secondary_context)

        if (value is None) and (inherit_none is not True) and context.parent:
            #
            # Search for the remaining path up through parents simulating inheritance.
            # Disable this behavior with the inherit_none flag. And if inherit_simple
            # is set then we only do this behavior for the last component of a path.
            # For example if we have this hierarchy:
            #
            #   - portal:
            #     - identity: identity_value
            #     - auth:
            #       - client: auth_client_value
            #     - smaht:
            #       - wolf:
            #         - some_property: some_property_value
            #
            # When we lookup /portal/smaht/wolf/identity we would get the value for /portal/identity,
            # identity_value, because it is visible within the /portal/smaht/wolf context; and if
            # we lookup /portal/wolf/auth/client we would get the value for /portal/auth/client,
            # auth_client_value, because it - /portal/auth - is also visible with that context.
            # Now if the inherit_simple flag is set then the first case gets the same result, but the
            # latter case - /portal/smaht/wolf/auth/client will return None because we would be looking
            # for a path with more than one component - auth/client - within the inherited/parent contexts.
            # The inherit_simple case is in case it turns out the that non-simple case is not very intuitive.
            #
            path_components_left = path_components[0:max(0, path_component_index - 1)]
            path_components_right = path_components[path_component_index:]
            if (inherit_simple is not True) or len(path_components_right) == 1:
                # This is a bit tricky; and note we lookup in parent but return current context.
                path_components = path_components_left + path_components_right
                path = self.repack_path(path_components, path_rooted=path_rooted)
                lookup_value, lookup_context = self._lookup(path, context=context.parent)
                if ConfigBasic._TRICKY_FIX and (lookup_value is not None):
                    context = ([context, *lookup_context]
                               if isinstance(lookup_context, list) else [context, lookup_context])
                return lookup_value, context

        return value, context

    def expand_macros(self, value: Any, context: Optional[JSON] = None) -> Any:
        # Note FYI that we do not macros the nested of macros.
        if isinstance(value, str):
            value = self._expand_macros_within_string(value, context)
        elif isinstance(value, JSON):
            for key in value:
                value[key] = self.expand_macros(value[key], value)
        return value

    def _expand_macros_within_string(self, value: str, context: Optional[JSON] = None) -> Any:

        def hide_macros(value: str, macro_values: Union[str, List[str]]) -> str:
            for macro_value in macro_values if isinstance(macro_values, (list, set)) else [macro_values]:
                value = value.replace(f"{ConfigBasic._MACRO_START}{macro_value}{ConfigBasic._MACRO_END}",
                                      f"{ConfigBasic._MACRO_HIDE_START}{macro_value}{ConfigBasic._MACRO_HIDE_END}")
            return value

        def unhide_macros(value: str) -> str:
            return (value.replace(ConfigBasic._MACRO_HIDE_START, ConfigBasic._MACRO_START)
                         .replace(ConfigBasic._MACRO_HIDE_END, ConfigBasic._MACRO_END))

        if not (isinstance(value, str) and value):
            return value

        expanding_macros = []
        missing_macro_found = False
        resolved_macro_context = None

        while True:
            if not ((match := ConfigBasic._MACRO_PATTERN.search(value)) and (macro_value := match.group(1))):
                break
            # This is a bit tricky with the context.
            resolved_macro_value, resolved_macro_context = self.lookup_macro(macro_value,
                                                                             context=resolved_macro_context or context)
            if resolved_macro_value is not None:
                if not is_primitive_type(resolved_macro_value):
                    self._warning(f"Macro must resolve to primitive type:"
                                  f" {self.path(context, macro_value)}", not self._ignore_structured_macros)
                    return value
                value = value.replace(f"${{{macro_value}}}", str(resolved_macro_value))
                if macro_value in expanding_macros:
                    self._warning(f"Circular macro definition found: {macro_value}", not self._ignore_circular_macros)
                    value = hide_macros(value, expanding_macros)
                    missing_macro_found = True
                else:
                    expanding_macros.append(macro_value)
            else:
                self._note_macro_not_found(macro_value, context)
                value = hide_macros(value, macro_value)
                missing_macro_found = True
        if missing_macro_found:
            value = unhide_macros(value)
        return value

    def lookup_macro(self, macro_value: str, context: Optional[JSON] = None) -> Tuple[Any, JSON]:
        if self.is_absolute_path(macro_value):
            resolved_macro_value = self.lookup(macro_value)
            resolved_macro_context = context
        else:
            resolved_macro_value, resolved_macro_context = self._lookup(macro_value, context=context)
            if (resolved_macro_value is None) and self._custom_macro_lookup:
                resolved_macro_value = self._custom_macro_lookup(macro_value, resolved_macro_context)
        if (resolved_macro_value is None) and self._includes:
            for include_item in self._includes:
                resolved_macro_value, resolved_macro_context = include_item.lookup_macro(macro_value)
                if resolved_macro_value is not None:
                    break
        return resolved_macro_value, resolved_macro_context

    def _note_macro_not_found(self, macro_value: str, context: Optional[JSON] = JSON) -> None:
        # TODO: one of tests ends up here with context as a list - why.
        self._warning(f"Macro not found: {macro_value}"
                      f"{f' (context: {context.path})' if isinstance(context, JSON) else ''}",
                      not self._ignore_missing_macros)

    def unpack_path(self, path: str) -> List[str]:
        return unpack_path(path, path_separator=self._path_separator,
                           path_current=ConfigBasic._PATH_COMPONENT_CURRENT,
                           path_parent=ConfigBasic._PATH_COMPONENT_PARENT)

    def repack_path(self, path_components: List[str], path_rooted: bool = False) -> str:
        return repack_path(path_components, path_rooted=path_rooted, path_separator=self._path_separator)

    def normalize_path(self, path: str) -> str:
        return self.repack_path(self.unpack_path(path))

    def is_absolute_path(self, path: str) -> bool:
        return isinstance(path, str) and path.startswith(self._path_separator)

    def context_path(self, context: JSON, path_suffix: Optional[str] = None) -> str:
        return context.context_path(path_rooted=True, path_suffix=path_suffix)

    def path(self, context: JSON, path_rooted: bool = True, path_suffix: Optional[str] = None) -> str:
        if not isinstance(context, JSON):
            return ""
        return context.context_path(path_separator=self._path_separator,
                                    path_rooted=path_rooted, path_suffix=path_suffix)

    def _warning(self, message: str, raise_exception: bool = False) -> None:
        if (raise_exception is True) or self._raise_exception:
            raise Exception(message)
        if isinstance(message, str) and message:
            message = f"WARNING: {message}"
        if message not in self._warnings:
            self._warnings.append(message)

    def _debug(self, message: str) -> None:
        if ("--debug" in sys.argv) or ("-debug" in sys.argv) or (os.environ.get("HMS_DEBUG", "").lower() == "true"):
            print(message, file=sys.stderr, flush=True)

    def _dump_for_testing(self, sorted: bool = False, verbose: bool = False, check: bool = False) -> None:
        self.data(sorted=sorted)._dump_for_testing(verbose=verbose, check=check)
