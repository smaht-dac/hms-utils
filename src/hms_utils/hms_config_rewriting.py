from __future__ import annotations
import json
import io
import os
import re
import sys
from typing import Any, List, Optional, Tuple, Union
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

    def __init__(self, config: JSON, path_separator: Optional[str] = None) -> None:
        if not (isinstance(path_separator, str) and (path_separator := path_separator.strip())):
            path_separator = Config._PATH_SEPARATOR
        if not isinstance(config, JSON):
            config = JSON(config) if isinstance(config, dict) else {}
        self._json = config
        self._path_separator = path_separator
        self._ignore_missing_macro = True

    def lookup_with_macro_expansion(self, path: str, config: Optional[JSON] = None) -> Optional[Union[Any, JSON]]:
        if not (value := self.lookup(path, config)):
            return None
        missing_macro_found = False
        while True:
            if not (match := Config._MACRO_PATTERN.search(value)):
                break
            if macro_value := match.group(1):
                if (resolved_macro_value := self.lookup(macro_value, config)) is not None:
                    if not is_primitive_type(resolved_macro_value):
                        warning(f"Macro must resolve to primitive type: {macro_value}")
                        return value
                    value = value.replace(f"${{{macro_value}}}", resolved_macro_value)
                elif self._ignore_missing_macro:
                    value = value.replace(f"{Config._MACRO_START}{macro_value}{Config._MACRO_END}",
                                          f"{Config._MACRO_HIDE_START}{macro_value}{Config._MACRO_HIDE_END}")
                else:
                    missing_macro_found = True
                    raise Exception(f"Macro not found: {macro_value}")
        if missing_macro_found and self._ignore_missing_macro:
            value = value.replace(Config._MACRO_HIDE_START, Config._MACRO_START)
            value = value.replace(Config._MACRO_HIDE_END, Config._MACRO_END)
        return value

    def lookup(self, path: str, config: Optional[JSON] = None) -> Optional[Union[Any, JSON]]:
        value, context = self._lookup(path, config)
        return value

    def _lookup(self, path: str, config: Optional[JSON] = None,
                parents: bool = False) -> Tuple[Optional[Union[Any, JSON]], JSON]:
        if (config is None) or (not isinstance(config, JSON)):
            config = self._json
        if (not (path_components := self.unpack_path(path))) or (path_components == [Config._PATH_COMPONENT_ROOT]):
            # No valid path or just the trival root ("/") path.
            return None, config
        if path_root := (path_components[0] == Config._PATH_COMPONENT_ROOT):
            config = config.root
            path_components = path_components[1:]
        value = context = None
        path_component_index_last = len(path_components) - 1
        for path_component_index, path_component in enumerate(path_components):
            context = config
            if (value := config.get(path_component)) is None:
                break
            if isinstance(value, JSON):
                # Found a JSON in the path so recurse down to it.
                config = value
            elif path_component_index < path_component_index_last:
                # Found a terminal (non-JSON) in the path but it is not the last component.
                value = None
                break
        if (value is None) and (path_component_index > 0) and (parents is not False):
            # Search for the remaining path up through parents simulating inheritance.
            path_components = path_components[0:path_component_index - 1] + path_components[path_component_index:]
            return self._lookup(self.repack_path(path_components, path_root), context.parent)
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
                        if len(path_components) > 1:
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


print(Config._normalize_path("//abc//def/ghi"))

DEFAULT_PATH_SEPARATOR = Config._PATH_SEPARATOR
# DEFAULT_CONFIG_FILE = os.path.expanduser("~/.config/hms/config.json")
# DEFAULT_SECRETS_FILE = os.path.expanduser("~/.config/hms/secrets.json")
DEFAULT_CONFIG_FILE = os.path.expanduser("~/repos/hms-utils/tests/data/config.json")
DEFAULT_SECRETS_FILE = os.path.expanduser("~/repos/hms-utils/tests/data/secrets.json")


with io.open(DEFAULT_CONFIG_FILE, "r") as f:
    config = JSON(json.load(f))
with io.open(DEFAULT_SECRETS_FILE, "r") as f:
    secrets = JSON(json.load(f))

config = Config(config)
secrets = Config(secrets)


def warning(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr, flush=True)


# path = "//abc/def/ghi/../../../../jkl/mno/.."
# print(Config._unpack_path(path))

path = "/portal/../portal/smaht//wolf"
path = "/portal/smaht/wolf/IDENTITY"
path = "/portal/smaht/xyzzy"
path = "/portal/smaht/identity/smaht/dev"
# value = config.lookup(path)
# print(f"{config.normalize_path(path)}: {value}")
value, context = config._lookup(path)
print(f"{config.normalize_path(path)}: {value} | {context}")

print()
path = "portal/smaht///wolf"
value = config.lookup(path)
print(f"{config.normalize_path(path)}: {value}")

print()
path = "portal/smaht///wolf/.."
value = config.lookup(path)
print(f"{config.normalize_path(path)}: {value}")

print()
path = "/s3/encrypt-key-id"
value = secrets.lookup(path)
print(f"{config.normalize_path(path)}: {value}")

print()
path = "foursight/cgap/dbmi/IDENTITY"
value = config.lookup_with_macro_expansion(path)
print(f"{config.normalize_path(path)}: {value}")
