import json
import io
import os
import re
import sys
from typing import Any, List, Optional, Tuple, Union
from hms_utils.dictionary_utils import JSON
from hms_utils.misc_utils import is_primitive_type

DEFAULT_PATH_SEPARATOR = "/"
# DEFAULT_CONFIG_FILE = os.path.expanduser("~/.config/hms/config.json")
# DEFAULT_SECRETS_FILE = os.path.expanduser("~/.config/hms/secrets.json")
DEFAULT_CONFIG_FILE = os.path.expanduser("~/repos/hms-utils/config.json")
DEFAULT_SECRETS_FILE = os.path.expanduser("~/repos/hms-utils/secrets.json")


class Config:

    _PATH_COMPONENT_PARENT = ".."
    _PATH_COMPONENT_CURRENT = "."
    _PATH_COMPONENT_ROOT = DEFAULT_PATH_SEPARATOR
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

    def __init__(self, config: JSON, path_separator: str = DEFAULT_PATH_SEPARATOR) -> None:
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
        if config is None:
            config = self._json
        value = config
        for path_component in self.unpack_path(path):
            if path_component == Config._PATH_COMPONENT_PARENT:
                value = value.parent
            elif (value := value.get(path_component)) is None:
                return None
        return value

    def _lookup(self, path: str, config: Optional[JSON] = None) -> Tuple[Optional[Union[Any, JSON]], JSON]:
        if config is None:
            config = self._json
        context = config
        context_current_only = False
        value = None
        if path_components := self.unpack_path(path):
            if path_components[0] == Config._PATH_COMPONENT_ROOT:
                context = context.root
                path_components = path_components[1:]
            elif path_components[0] == Config._PATH_COMPONENT_CURRENT:
                context_current_only = True
                path_components = path_components[1:]
            path_components_last_index = len(path_components) - 1
            for path_component_index, path_component in enumerate(path_components):
                if path_component == Config._PATH_COMPONENT_PARENT:
                    if (context := context.parent) is None:
                        return None, None
                elif (value := context.get(path_component)) is not None:
                    if isinstance(value, JSON):
                        context = value
                    elif path_component_index == path_components_last_index:
                        return value, context
                    else:
                        # Found terminal (non-dictionary) value but not last in path so not found.
                        return None, context
                else:
                    return None, context
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
        path_components = []
        if isinstance(path, str) and (path := path.strip()):
            if path.startswith(Config._PATH_COMPONENT_ROOT):
                path = path[len(Config._PATH_COMPONENT_ROOT):]
                path_components.append(Config._PATH_COMPONENT_ROOT)
            for path_component in path.split(self._path_separator):
                if (path_component := path_component.strip()):
                    path_components.append(path_component)
        return path_components

    def repack_path(self, path_components: List[str]) -> str:
        if isinstance(path_components, list) and path_components:
            if path_components[0] == self._path_separator:
                return self._path_separator + self._path_separator.join(path_components[1:])
            else:
                return self._path_separator.join(path_components)
        return ""

    def normalize_path(self, path: str) -> List[str]:
        return self.repack_path(self.unpack_path(path))


with io.open(DEFAULT_CONFIG_FILE, "r") as f:
    config = JSON(json.load(f))
with io.open(DEFAULT_SECRETS_FILE, "r") as f:
    secrets = JSON(json.load(f))

config = Config(config)
secrets = Config(secrets)


def warning(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr, flush=True)

path = "/portal/../portal/smaht//wolf"
path = "//portal/smaht//wolf"
config.unpack_path(path)
value = config.lookup(path)
print(f"{config.normalize_path(path)}: {value}")

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
