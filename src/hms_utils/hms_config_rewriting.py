from __future__ import annotations
from boto3 import client as BotoClient
import io
import json
import os
import re
import sys
from typing import Any, Callable, List, Optional, Tuple, Union
from hms_utils.dictionary_utils import JSON
from hms_utils.misc_utils import is_primitive_type

# UNDER DEVELOPMENT: Basically rewriting hms_config to be tighter based on lessons learned.


class Config:

    _POSSIBLE_TRICKY_FIX = True
    _PATH_SEPARATOR = "/"
    _PATH_COMPONENT_PARENT = ".."
    _PATH_COMPONENT_CURRENT = "."
    _PATH_COMPONENT_ROOT = _PATH_SEPARATOR
    _MACRO_START = "${"
    _MACRO_END = "}"
    _MACRO_PATTERN = re.compile(r"\$\{([^}]+)\}")
    _MACRO_HIDE_START = "@@@__["
    _MACRO_HIDE_END = "]__@@@"
    _MACRO_PATTERN = re.compile(r"\$\{([^}]+)\}")

    def __init__(self, config: JSON, path_separator: Optional[str] = None,
                 custom_macro_lookup: Optional[Callable] = None,
                 warning: Optional[Union[Callable, bool]] = None, exception: bool = False) -> None:
        if not (isinstance(path_separator, str) and (path_separator := path_separator.strip())):
            path_separator = Config._PATH_SEPARATOR
        if not isinstance(config, JSON):
            if isinstance(config, str) and os.path.isfile(config):
                try:
                    with io.open(config, "r") as f:
                        config = json.load(f)
                except Exception:
                    pass
            config = JSON(config) if isinstance(config, dict) else {}
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

    def merge(self, json: JSON) -> None:
        if isinstance(json, JSON):
            self._json = self._json.merge(json)

    @property
    def json(self) -> JSON:
        return self._json

    def lookup(self, path: str, context: Optional[JSON] = None,
               noexpand: bool = False, simple: bool = False, noinherit: bool = False) -> Optional[Union[Any, JSON]]:
        value, context = self._lookup(path, context, simple=simple, noinherit=noinherit)
        return value if ((value is None) or (noexpand is True)) else self._expand_macros(value, context)

    def _lookup(self, path: str, context: Optional[JSON] = None,
                simple: bool = False, noinherit: bool = False) -> Tuple[Optional[Union[Any, JSON]], JSON]:
        # TODO: _POSSIBLE_TRICKY_FIX ...
        # If we do stick with this we should make this a list of any length.
        context_alternate = None
        if isinstance(context, list):
            context_alternate = context[1]
            context = context[0]
        # ... TODO: _POSSIBLE_TRICKY_FIX
        if (context is None) or (not isinstance(context, JSON)):
            context = self._json
        value = None
        if not (path_components := self.unpack_path(path)):
            # No or invalid path.
            return value, context
        if path_root := (path_components[0] == Config._PATH_COMPONENT_ROOT):
            if len(path_components) == 1:
                # Trivial case of just the root path ("/").
                return value, context
            context = context.root
            path_components = path_components[1:]
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
        if Config._POSSIBLE_TRICKY_FIX and (value is None) and isinstance(context_alternate, JSON):
            # If we do stick with this fix need to make this alternate context thing a proper list of any length.
            for path_component_index, path_component in enumerate(path_components):
                if (value := context_alternate.get(path_component)) is None:
                    break
                if isinstance(value, JSON):
                    # Found a JSON in the path so recurse down to it.
                    context_alternate = value
                elif path_component_index < (len(path_components) - 1):
                    # Found a terminal (non-JSON) in the path but it is not the last component.
                    value = None
                    break
        if (value is None) and (noinherit is not True) and context.parent:
            #
            # Search for the remaining path up through parents simulating inheritance.
            # Disable this behavior with the noinherit flag. And if the simple flag
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
            # Now if the simple flag is set then the first case gets the same result, but the latter
            # case - /portal/smaht/wolf/auth/client will return None because we would be looking for
            # a path with more than one component - auth/client - within the inherited/parent contexts.
            # The simple case is in case it turns out the that non-simple case is not very intuitive.
            #
            path_components_left = path_components[0:max(0, path_component_index - 1)]
            path_components_right = path_components[path_component_index:]
            if (simple is not True) or len(path_components_right) == 1:
                # This is a bit tricky; and note we lookup in parent but return current context.
                path_components = path_components_left + path_components_right
                path = self.repack_path(path_components, root=path_root)
                lookup_value, lookup_context = self._lookup(path, context=context.parent)
                if Config._POSSIBLE_TRICKY_FIX and (lookup_value is not None):
                    context = ([context, *lookup_context]
                               if isinstance(lookup_context, list) else [context, lookup_context])
                return lookup_value, context
        return value, context

    def _expand_macros(self, value: Any, context: Optional[JSON] = None) -> Any:
        if isinstance(value, str):
            value = self._expand_macros_within_string(value, context)
        elif isinstance(value, JSON):
            for key in value:
                value[key] = self._expand_macros(value[key], value)
        return value

    def _expand_macros_within_string(self, value: str, context: Optional[JSON] = None) -> Any:
        if not (isinstance(value, str) and value):
            return value
        expanding_macros = []
        missing_macro_found = False
        resolved_macro_context = None
        while True:
            if not ((match := Config._MACRO_PATTERN.search(value)) and (macro_value := match.group(1))):
                break
            # This is a bit tricky with the context.
            resolved_macro_value, resolved_macro_context = self._lookup_macro(macro_value,
                                                                              context=resolved_macro_context or context)
            if resolved_macro_value is not None:
                if not is_primitive_type(resolved_macro_value):
                    self._warning(f"Macro must resolve to primitive type: {self.context_path(context, macro_value)}",
                                  not self._ignore_structured_macros)
                    return value
                value = value.replace(f"${{{macro_value}}}", str(resolved_macro_value))
                if macro_value in expanding_macros:
                    self._warning(f"Circular macro definition found: {macro_value}", not self._ignore_circular_macros)
                    value = self._hide_macros(value, expanding_macros)
                    missing_macro_found = True
                else:
                    expanding_macros.append(macro_value)
            else:
                self._warning(f"Macro not found: {macro_value}", not self._ignore_missing_macros)
                value = self._hide_macros(value, macro_value)
                missing_macro_found = True
        if missing_macro_found:
            value = self._unhide_macros(value)
        return value

    def _hide_macros(self, value: str, macro_values: Union[str, List[str]]) -> str:
        for macro_value in macro_values if isinstance(macro_values, (list, set)) else [macro_values]:
            return value.replace(f"{Config._MACRO_START}{macro_value}{Config._MACRO_END}",
                                 f"{Config._MACRO_HIDE_START}{macro_value}{Config._MACRO_HIDE_END}")

    def _unhide_macros(self, value: str) -> str:
        return (value.replace(Config._MACRO_HIDE_START, Config._MACRO_START)
                     .replace(Config._MACRO_HIDE_END, Config._MACRO_END))

    def _lookup_macro(self, macro_value: str, context: Optional[JSON] = None) -> Any:
        resolved_macro_value, resolved_macro_context = self._lookup(macro_value, context=context)
        if (resolved_macro_value is None) and self._custom_macro_lookup:
            resolved_macro_value = self._custom_macro_lookup(macro_value, resolved_macro_context)
        return resolved_macro_value, resolved_macro_context

    def unpack_path(self, path: str) -> List[str]:
        return Config._unpack_path(path, path_separator=self._path_separator)

    def repack_path(self, path_components: List[str], root: bool = False) -> str:
        return Config._repack_path(path_components, root=root, path_separator=self._path_separator)

    def normalize_path(self, path: str) -> List[str]:
        return self.repack_path(self.unpack_path(path))

    def context_path(self, context: JSON, path: Optional[str] = None) -> Optional[str]:
        return Config._context_path(context, path, path_separator=self._path_separator)

    @staticmethod
    def _unpack_path(path: str, path_separator: Optional[str] = None) -> List[str]:
        if not (isinstance(path_separator, str) and (path_separator := path_separator.strip())):
            path_separator = Config._PATH_SEPARATOR
        path_components = []
        if isinstance(path, str) and (path := path.strip()):
            if path.startswith(Config._PATH_COMPONENT_ROOT):
                path = path[len(Config._PATH_COMPONENT_ROOT):]
                path_components.append(Config._PATH_COMPONENT_ROOT)
            for path_component in path.split(path_separator):
                if ((path_component := path_component.strip()) and (path_component != Config._PATH_COMPONENT_CURRENT)):
                    if path_component == Config._PATH_COMPONENT_PARENT:
                        if (len(path_components) > 0) and (path_components != [Config._PATH_COMPONENT_ROOT]):
                            path_components = path_components[:-1]
                        continue
                    path_components.append(path_component)
        return path_components

    @staticmethod
    def _repack_path(path_components: List[str], root: bool = False, path_separator: Optional[str] = None) -> str:
        if not (isinstance(path_separator, str) and (path_separator := path_separator.strip())):
            path_separator = Config._PATH_SEPARATOR
        if not (isinstance(path_components, list) and path_components):
            path_components = []
        if path_components[0] == Config._PATH_COMPONENT_ROOT:
            root = True
            path_components = path_components[1:]
        return (path_separator if root else "") + path_separator.join(path_components)

    @staticmethod
    def _normalize_path(path: str, path_separator: Optional[str] = None) -> List[str]:
        return Config._repack_path(Config._unpack_path(path, path_separator), path_separator)

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


class ConfigWithAwsMacroExpander(Config):

    _AWS_SECRET_MACRO_NAME_PREFIX = "aws-secret:"
    _AWS_SECRET_MACRO_START = f"{Config._MACRO_START}{_AWS_SECRET_MACRO_NAME_PREFIX}"
    _AWS_SECRET_MACRO_END = Config._MACRO_END
    _AWS_SECRET_MACRO_PATTERN = re.compile(r"\$\{aws-secret:([^}]+)\}")
    _AWS_SECRET_NAME_NAME = "IDENTITY"

    def __init__(self, config: JSON, path_separator: Optional[str] = None,
                 noaws: bool = False, raise_exception: bool = False,
                 warning: Optional[Union[Callable, bool]] = None) -> None:
        super().__init__(config, path_separator=path_separator,
                         custom_macro_lookup=self._lookup_macro_custom, warning=warning)
        self._noaws = noaws is True
        self._raise_exception = raise_exception is True

    def _lookup_macro_custom(self, macro_value: str, context: Optional[JSON] = None) -> Any:
        if not macro_value.startswith(ConfigWithAwsMacroExpander._AWS_SECRET_MACRO_NAME_PREFIX):
            return None
        secret_specifier = macro_value[len(ConfigWithAwsMacroExpander._AWS_SECRET_MACRO_NAME_PREFIX):]
        return self._lookup_aws_secret(secret_specifier, context)

    def _lookup_aws_secret(self, secret_specifier: str, context: str) -> Optional[str]:
        if (index := secret_specifier.find(self._path_separator)) > 0:
            secret_name = secret_specifier[index + 1:]
            secrets_name = secret_specifier[0:index]
        else:
            secret_name = secret_specifier
            secrets_name = self.lookup(ConfigWithAwsMacroExpander._AWS_SECRET_NAME_NAME, context)
        return self._aws_get_secret(secrets_name, secret_name)

    def _aws_get_secret(self, secrets_name: str, secret_name: str) -> Optional[str]:
        if self._noaws:
            return None
        try:
            boto_secrets = BotoClient("secretsmanager")
            secrets = boto_secrets.get_secret_value(SecretId=secrets_name)
            secrets = json.loads(secrets.get("SecretString"))
            return secrets[secret_name]
        except Exception as e:
            if self._raise_exception is True:
                raise e
            self._warning(f"Cannot find AWS secret: {secrets_name}/{secret_name}")
        return None
