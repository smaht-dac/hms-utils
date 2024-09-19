from __future__ import annotations
import re
import sys
from typing import Any, Callable, List, Optional, Tuple, Union
from hms_utils.dictionary_utils import JSON, load_json_file
from hms_utils.misc_utils import is_primitive_type
from hms_utils.config.utils import repack_path, unpack_path

# UNDER DEVELOPMENT: Basically rewriting hms_config to be tighter based on lessons learned.


class Config:

    _PATH_SEPARATOR = "/"
    _PATH_COMPONENT_CURRENT = "."
    _PATH_COMPONENT_PARENT = ".."
    _PATH_COMPONENT_ROOT = _PATH_SEPARATOR
    _MACRO_START = "${"
    _MACRO_END = "}"
    _MACRO_PATTERN = re.compile(r"\$\{([^}]+)\}")
    _MACRO_HIDE_START = "@@@__["
    _MACRO_HIDE_END = "]__@@@"
    _MACRO_PATTERN = re.compile(r"\$\{([^}]+)\}")
    _TRICKY_FIX = True

    def __init__(self, config: JSON,
                 tag: Optional[Tuple[str, Any]] = None,
                 path_separator: Optional[str] = None,
                 custom_macro_lookup: Optional[Callable] = None,
                 warning: Optional[Union[Callable, bool]] = None, exception: bool = False) -> None:
        if not (isinstance(path_separator, str) and (path_separator := path_separator.strip())):
            path_separator = Config._PATH_SEPARATOR
        if not isinstance(config, JSON):
            if isinstance(config, str):
                config = load_json_file(config)
            elif not isinstance(config, dict):
                raise Exception("Must create Config object with dictionary, JSON, or file path.")
            config = JSON(config) if isinstance(config, dict) else JSON({})
        self._json = config
        self._path_separator = path_separator
        self._custom_macro_lookup = custom_macro_lookup if callable(custom_macro_lookup) else None
        self._ignore_missing_macros = True
        self._ignore_circular_macros = True
        self._ignore_structured_macros = True
        self._warning = (warning if callable(warning) else (self._warn if warning is True else lambda _, __=None: _))
        self._exception = exception is True
        if self._exception:
            self._warning = self._warn
        self.tag(tag)

    @property
    def json(self) -> JSON:
        return self._json

    def tag(self, tag: Optional[Tuple[str, Any]] = None) -> None:
        if isinstance(tag, tuple) and (len(tag) == 2):
            if isinstance(tag_name := tag[0], str) and (tag_name := tag_name.strip()):
                if self._json.tag(tag_name, tag[1]):
                    setattr(self, tag_name, tag[1])
        elif isinstance(tag, str) and (tag := tag.strip()):
            if self._json.tag(tag, True):
                setattr(self, tag, True)

    def merge(self, json: Union[JSON, dict]) -> None:
        if isinstance(json, dict):
            json = JSON(json)
        if isinstance(json, JSON):
            self._json = self._json.merge(json)

    def lookup(self, path: str, context: Optional[JSON] = None, noexpand: bool = False,
               inherit_simple: bool = False, inherit_none: bool = False) -> Optional[Union[Any, JSON]]:
        value, context = self._lookup(path, context, inherit_simple=inherit_simple, inherit_none=inherit_none)
        return value if ((value is None) or (noexpand is True)) else self.expand_macros(value, context)

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
        if path_root := (path_components[0] == Config._PATH_COMPONENT_ROOT):
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
                path = self.repack_path(path_components, root=path_root)
                lookup_value, lookup_context = self._lookup(path, context=context.parent)
                if Config._TRICKY_FIX and (lookup_value is not None):
                    context = ([context, *lookup_context]
                               if isinstance(lookup_context, list) else [context, lookup_context])
                return lookup_value, context

        return value, context

    def expand_macros(self, value: Any, context: Optional[JSON] = None) -> Any:
        if isinstance(value, str):
            value = self._expand_macros_within_string(value, context)
        elif isinstance(value, JSON):
            for key in value:
                value[key] = self.expand_macros(value[key], value)
        return value

    def _expand_macros_within_string(self, value: str, context: Optional[JSON] = None) -> Any:

        def hide_macros(value: str, macro_values: Union[str, List[str]]) -> str:
            for macro_value in macro_values if isinstance(macro_values, (list, set)) else [macro_values]:
                value = value.replace(f"{Config._MACRO_START}{macro_value}{Config._MACRO_END}",
                                      f"{Config._MACRO_HIDE_START}{macro_value}{Config._MACRO_HIDE_END}")
            return value

        def unhide_macros(value: str) -> str:
            return (value.replace(Config._MACRO_HIDE_START, Config._MACRO_START)
                         .replace(Config._MACRO_HIDE_END, Config._MACRO_END))

        if not (isinstance(value, str) and value):
            return value

        expanding_macros = []
        missing_macro_found = False
        resolved_macro_context = None

        while True:
            if not ((match := Config._MACRO_PATTERN.search(value)) and (macro_value := match.group(1))):
                break
            # This is a bit tricky with the context.
            resolved_macro_value, resolved_macro_context = self.lookup_macro(macro_value,
                                                                             context=resolved_macro_context or context)
            if resolved_macro_value is not None:
                if not is_primitive_type(resolved_macro_value):
                    self._warning(f"Macro must resolve to primitive type:"
                                  f"{self.context_path(context, macro_value)}", not self._ignore_structured_macros)
                    return value
                value = value.replace(f"${{{macro_value}}}", str(resolved_macro_value))
                if macro_value in expanding_macros:
                    self._warning(f"Circular macro definition found: {macro_value}", not self._ignore_circular_macros)
                    value = hide_macros(value, expanding_macros)
                    missing_macro_found = True
                else:
                    expanding_macros.append(macro_value)
            else:
                self._warning(f"Macro not found: {macro_value}", not self._ignore_missing_macros)
                value = hide_macros(value, macro_value)
                missing_macro_found = True
        if missing_macro_found:
            value = unhide_macros(value)
        return value

    def lookup_macro(self, macro_value: str, context: Optional[JSON] = None) -> Tuple[Any, JSON]:
        if self.is_absolute_path(macro_value):
            return self.lookup(macro_value), context
        resolved_macro_value, resolved_macro_context = self._lookup(macro_value, context=context)
        if (resolved_macro_value is None) and self._custom_macro_lookup:
            resolved_macro_value = self._custom_macro_lookup(macro_value, resolved_macro_context)
        return resolved_macro_value, resolved_macro_context

    def unpack_path(self, path: str) -> List[str]:
        return unpack_path(path, path_separator=self._path_separator,
                           path_current=Config._PATH_COMPONENT_CURRENT, path_parent=Config._PATH_COMPONENT_PARENT)

    def repack_path(self, path_components: List[str], root: bool = False) -> str:
        return repack_path(path_components, root=root, path_separator=self._path_separator)

    def normalize_path(self, path: str) -> str:
        return self.repack_path(self.unpack_path(path))

    def is_absolute_path(self, path: str) -> bool:
        return isinstance(path, str) and path.startswith(self._path_separator)

    def context_path(self, context: JSON, path: Optional[str] = None) -> Optional[str]:
        return Config._context_path(context, path, path_separator=self._path_separator)

    @staticmethod
    def _context_path(context: JSON, path: Optional[str] = None, path_separator: Optional[str] = None) -> Optional[str]:
        if not (context_path := context.context_path):
            return None
        if not (isinstance(path_separator, str) and (path_separator := path_separator.strip())):
            path_separator = Config._PATH_SEPARATOR
        if isinstance(path, str):
            context_path.append(path)
        return f"{path_separator}{path_separator.join(context_path)}"

    def _warn(self, message: str, exception: bool = False) -> None:
        print(f"WARNING: {message}", file=sys.stderr, flush=True)
        if (exception is True) or (self._exception is True):
            raise Exception(message)


config = Config({
    "abc": {
        "def": "def_value"
    },
    "ghi": {
        "jkl": "jkl_value_${/abc/def}_${abc/def}"
    }
}, tag=("secret", True))
# }, tag="secret")

x = config.lookup("/ghi/jkl")
print(x)
print(f"[{config.json.secret}]")
print(config.json["abc"].secret)
print(config.json["ghi"].secret)
