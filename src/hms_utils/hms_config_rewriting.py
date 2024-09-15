from __future__ import annotations
import re
import sys
from typing import Any, Callable, List, Optional, Tuple, Union
from hms_utils.dictionary_utils import JSON
from hms_utils.misc_utils import is_primitive_type


class Config:

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
    _AWS_SECRET_MACRO_NAME_PREFIX = "aws-secret:"
    _AWS_SECRET_MACRO_START = f"{_MACRO_START}{_AWS_SECRET_MACRO_NAME_PREFIX}"
    _AWS_SECRET_MACRO_END = _MACRO_END
    _AWS_SECRET_MACRO_PATTERN = re.compile(r"\$\{aws-secret:([^}]+)\}")
    _AWS_SECRET_NAME_NAME = "IDENTITY"
    _IMPORTED_CONFIG_KEY_PREFIX = "@@@__CONFIG__:"
    _IMPORTED_SECRETS_KEY_PREFIX = "@@@__SECRETS__:"

    def __init__(self, config: JSON, path_separator: Optional[str] = None,
                 warning: Optional[Union[Callable, bool]] = None) -> None:
        if not (isinstance(path_separator, str) and (path_separator := path_separator.strip())):
            path_separator = Config._PATH_SEPARATOR
        if not isinstance(config, JSON):
            config = JSON(config) if isinstance(config, dict) else {}
        self._json = config
        self._path_separator = path_separator
        self._ignore_missing_macro = True
        self._warning = (warning if callable(warning)
                         else (lambda message: print(message, file=sys.stderr, flush=True)
                               if warning is True else lambda message: None))

    def lookup(self, path: Union[str, List[str]], config: Optional[JSON] = None,
               expand: bool = True, simple: bool = False, noinherit: bool = False) -> Optional[Union[Any, JSON]]:
        value, context = self._lookup(path, config, simple=simple, noinherit=noinherit)
        if (value is None) or (expand is False):
            return value
        missing_macro_found = False
        while True:
            if (not isinstance(value, str)) or (not (match := Config._MACRO_PATTERN.search(value))):
                break
            if macro_value := match.group(1):
                resolved_macro_value, resolved_macro_context = self._lookup(macro_value, config=context)
                if resolved_macro_value is not None:
                    if not is_primitive_type(resolved_macro_value):
                        self._warning(f"Macro must resolve to primitive type: {macro_value}")
                        return value
                    value = value.replace(f"${{{macro_value}}}", resolved_macro_value)
                elif self._ignore_missing_macro:
                    value = value.replace(f"{Config._MACRO_START}{macro_value}{Config._MACRO_END}",
                                          f"{Config._MACRO_HIDE_START}{macro_value}{Config._MACRO_HIDE_END}")
                    missing_macro_found = True
                else:
                    raise Exception(f"Macro not found: {macro_value}")
        if missing_macro_found and self._ignore_missing_macro:
            value = value.replace(Config._MACRO_HIDE_START, Config._MACRO_START)
            value = value.replace(Config._MACRO_HIDE_END, Config._MACRO_END)
        return value

    def _lookup(self, path: Union[str, List[str]], config: Optional[JSON] = None,
                simple: bool = False, noinherit: bool = False) -> Tuple[Optional[Union[Any, JSON]], JSON]:
        if (config is None) or (not isinstance(config, JSON)):
            config = self._json
        value = None ; context = config  # noqa
        if isinstance(path, list):
            # Actually allow the path to the path-components.
            if not (path_components := path):
                return value, context
        elif not (path_components := self.unpack_path(path)):
            return value, context
        if path_root := (path_components[0] == Config._PATH_COMPONENT_ROOT):
            if len(path_components) == 1:
                # Trivial case of just the root path ("/").
                return value, context
            config = config.root
            path_components = path_components[1:]
        for path_component_index, path_component in enumerate(path_components):
            context = config
            if (value := config.get(path_component)) is None:
                break
            if isinstance(value, JSON):
                # Found a JSON in the path so recurse down to it.
                config = value
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
            path_components_left = path_components[0:path_component_index - 1]
            path_components_right = path_components[path_component_index:]
            if (simple is not True) or len(path_components_right) == 1:
                path_components = path_components_left + path_components_right
                path = self.repack_path(path_components, root=path_root)
                return self._lookup(path, config=context.parent)
        return value, context

    def lookup_macro(self, macro_value: str, config: Optional[JSON] = None) -> Optional[Union[Any, JSON]]:
        if config is None:
            config = self._json
        if (macro_value := self.lookup(macro_value, config)) is not None:
            return macro_value
            # if is_primitive_type(macro_value):
            #     return macro_value
            # return None
        return None

    def unpack_path(self, path: str) -> List[str]:
        return Config._unpack_path(path, path_separator=self._path_separator)

    def repack_path(self, path_components: List[str], root: bool = False) -> str:
        return Config._repack_path(path_components, root=root, path_separator=self._path_separator)

    def normalize_path(self, path: str) -> List[str]:
        return self.repack_path(self.unpack_path(path))

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
