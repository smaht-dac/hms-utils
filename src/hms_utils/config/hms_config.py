from __future__ import annotations
import os
import re
import sys
from typing import Any, Callable, List, Optional, Tuple, Union
from hms_utils.config.utils import repack_path, unpack_path
from hms_utils.dictionary_utils import load_json_file
from hms_utils.dictionary_parented import DictionaryParented as JSON
from hms_utils.type_utils import is_primitive_type, primitive_type

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
    _SECRET_VALUE = "********"
    _SECRET_VALUE_START = "@@@__secret_start__@@@["
    _SECRET_VALUE_END = "]@@@__secret_end__@@@"
    _SECRET_VALUE_START_LENGTH = len(_SECRET_VALUE_START)
    _SECRET_VALUE_END_LENGTH = len(_SECRET_VALUE_END)
    _TRICKY_FIX = True

    def __init__(self, config: Union[dict, str],
                 name: Optional[str] = None,
                 secrets: bool = False,
                 path_separator: Optional[str] = None,
                 custom_macro_lookup: Optional[Callable] = None,
                 warning: Optional[Union[Callable, bool]] = None, exception: bool = False) -> None:
        if not (isinstance(path_separator, str) and (path_separator := path_separator.strip())):
            path_separator = Config._PATH_SEPARATOR
        if isinstance(config, str):
            if (secrets is not True) and ("secret" in os.path.basename(config)):
                secrets = True
            config = load_json_file(config)
        elif not isinstance(config, dict):
            raise Exception("Must create Config object with dictionary, JSON, or file path.")
        self._secrets = secrets is True
        self._json = JSON(config, rvalue=Config._secrets_encoded if self.secrets else None)
        self._name = name if isinstance(name, str) and name else None
        self._imports = None
        self._path_separator = path_separator
        self._custom_macro_lookup = custom_macro_lookup if callable(custom_macro_lookup) else None
        self._ignore_missing_macros = True
        self._ignore_circular_macros = True
        self._ignore_structured_macros = True
        self._warning = (warning if callable(warning) else (self._warn if warning is True else lambda _, __=None: _))
        self._exception = exception is True
        if self._exception:
            self._warning = self._warn

    def data(self, show: Optional[bool] = False) -> JSON:
        if show is True:
            return JSON(self._json, rvalue=Config._secrets_plaintext)
        elif show is False:
            return JSON(self._json, rvalue=Config._secrets_obfuscated)
        return self._json

    @property
    def json(self) -> JSON:
        return self._json

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def secrets(self) -> bool:
        return self._secrets

    def merge(self, data: Union[Union[dict, Config],
                                List[Union[dict, Config]]]) -> Tuple[List[str], List[str], List[str]]:
        merged_secret_paths = [] ; merged_paths = [] ; unmerged_paths = []  # noqa
        if isinstance(data, (dict, Config)):
            data = [data]
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    item = JSON(item)
                elif isinstance(item, Config):
                    self._secrets = item.secrets
                    item = item._json
                if isinstance(item, JSON):
                    self._json, item_merged_paths, item_unmerged_paths = (
                        self._json.merge(item, path_separator=self._path_separator))
                    if self._secrets:
                        merged_secret_paths.extend(item_merged_paths)
                    merged_paths.extend(item_merged_paths)
                    unmerged_paths.extend(item_unmerged_paths)
        return merged_secret_paths, merged_paths, unmerged_paths

    def imports(self, data: Union[List[Union[dict, Config]], Union[dict, Config]]) -> None:
        if isinstance(data, (dict, Config)):
            data = [data]
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    item = JSON(dict)
                elif isinstance(item, Config):
                    item = item._json
                if isinstance(item, JSON):
                    if self._imports is None:
                        self._imports = []
                    self._imports.append(Config(item))

    def lookup(self, path: str, show: Optional[bool] = False, noexpand: bool = False,
               inherit_simple: bool = False, inherit_none: bool = False) -> Optional[Union[Any, JSON]]:
        value, context = self._lookup(path, self._json, inherit_simple=inherit_simple, inherit_none=inherit_none)
        value = value if ((value is None) or (noexpand is True)) else self.expand_macros(value, context)
        if value is None:
            return value
        elif show is True:
            if isinstance(value, JSON):
                return value.asdict(rvalue=Config._secrets_plaintext)
            else:
                return Config._secrets_plaintext(value)
        elif show is False:
            if isinstance(value, JSON):
                return value.asdict(rvalue=Config._secrets_obfuscated)
            else:
                return Config._secrets_obfuscated(value)
        else:
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
            resolved_macro_value = self.lookup(macro_value)
            resolved_macro_context = context
        else:
            resolved_macro_value, resolved_macro_context = self._lookup(macro_value, context=context)
            if (resolved_macro_value is None) and self._custom_macro_lookup:
                resolved_macro_value = self._custom_macro_lookup(macro_value, resolved_macro_context)
        if (resolved_macro_value is None) and self._imports:
            for import_item in self._imports:
                resolved_macro_value, resolved_macro_context = import_item.lookup_macro(macro_value)
                if resolved_macro_value is not None:
                    break
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

    def context_path(self, context: JSON, path: Optional[str] = None) -> str:
        return context.path(path_separator=self._path_separator, path_rooted=True, path=path)

    def _warn(self, message: str, exception: bool = False) -> None:
        print(f"WARNING: {message}", file=sys.stderr, flush=True)
        if (exception is True) or (self._exception is True):
            raise Exception(message)

    # All of this secrets stuff is just so that when obtaining values (print/dump or lookup), any
    # strings which came from a "secret" configuration can be obfuscated by default, or shown if desired.

    @staticmethod
    def _secrets_encoded(value: primitive_type) -> str:
        if not is_primitive_type(value):
            return ""
        if (value_type := type(value).__name__) != "str":
            return f"{Config._SECRET_VALUE_START}{value_type}:{value}{Config._SECRET_VALUE_END}"
        secrets_encoded = ""
        start = 0
        while True:
            if not (match := Config._MACRO_PATTERN.search(value[start:])):
                # secrets_encoded += value[start:]
                if secret_part := value[start:]:
                    secrets_encoded += f"{Config._SECRET_VALUE_START}str:{secret_part}{Config._SECRET_VALUE_END}"
                break
            match_start = match.start()
            match_end = match.end()
            macro_part = value[start + match_start:start + match_end]
            if secret_part := value[start:start + match_start]:
                secrets_encoded += f"{Config._SECRET_VALUE_START}str:{secret_part}{Config._SECRET_VALUE_END}"
            secrets_encoded += macro_part
            start += match_end
        return secrets_encoded

    @staticmethod
    def _secrets_plaintext(secrets_encoded: Any) -> primitive_type:
        if (not isinstance(secrets_encoded, str)) or (not secrets_encoded):
            return secrets_encoded
        secret_value_typed = None
        while True:
            if (start := secrets_encoded.find(Config._SECRET_VALUE_START)) < 0:
                break
            if (end := secrets_encoded.find(Config._SECRET_VALUE_END)) < start:
                break
            secret_value = secrets_encoded[start + Config._SECRET_VALUE_START_LENGTH:end]
            if secret_value.startswith("str:"):
                secret_value = secret_value[4:]
            elif secret_value.startswith("int:"):
                secret_value = secret_value[4:]
                secret_value_typed = int(secret_value)
            elif secret_value.startswith("float:"):
                secret_value = secret_value[6:]
                secret_value_typed = float(secret_value)
            elif secret_value.startswith("bool:"):
                secret_value = secret_value[5:]
                secret_value_typed = True if (secret_value.lower() == "true") else False
            secrets_encoded = (
                secrets_encoded[0:start] + secret_value +
                secrets_encoded[end + Config._SECRET_VALUE_END_LENGTH:])
        if (secret_value_typed is not None) and (str(secret_value_typed) == secret_value):
            return secret_value_typed
        return secrets_encoded

    @staticmethod
    def _secrets_obfuscated(secrets_encoded: str, obfuscated_value: Optional[str] = None) -> str:
        if (not isinstance(secrets_encoded, str)) or (not secrets_encoded):
            return ""
        if (not isinstance(obfuscated_value, str)) or (not obfuscated_value):
            obfuscated_value = Config._SECRET_VALUE
        while True:
            if (start := secrets_encoded.find(Config._SECRET_VALUE_START)) < 0:
                break
            if (end := secrets_encoded.find(Config._SECRET_VALUE_END)) < start:
                break
            obfuscated = obfuscated_value if end > start + Config._SECRET_VALUE_START_LENGTH else ""
            secrets_encoded = (
                secrets_encoded[0:start] + obfuscated +
                secrets_encoded[end + Config._SECRET_VALUE_END_LENGTH:])
        return secrets_encoded

    def _dump_for_testing(self, show: bool = False, verbose: bool = False, check: bool = False) -> None:
        if show is True:
            json = JSON(self._json, rvalue=Config._secrets_plaintext)
        elif show is False:
            json = JSON(self._json, rvalue=Config._secrets_obfuscated)
        else:
            json = self._json
        json._dump_for_testing(verbose=verbose, check=check)
