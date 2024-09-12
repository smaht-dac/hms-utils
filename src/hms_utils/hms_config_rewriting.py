import json
import io
import os
import re
from typing import Any, List, Optional, Union
from hms_utils.dictionary_utils import JSON

DEFAULT_PATH_SEPARATOR = "/"
PATH_PARENT_COMPONENT = ".."
DEFAULT_CONFIG_FILE = os.path.expanduser("~/.config/hms/config.json")
DEFAULT_SECRETS_FILE = os.path.expanduser("~/.config/hms/secrets.json")


class Config:

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
        while True:
            if not (match := Config._MACRO_PATTERN.search(value)):
                break
            if macro_value := match.group(1):
                if (resolved_macro_value := self.lookup(macro_value)):
                    import pdb ; pdb.set_trace()  # noqa
                    value = value.replace(f"${{{macro_value}}}", resolved_macro_value)
                    pass
        return value

    def lookup(self, path: str, config: Optional[JSON] = None) -> Optional[Union[Any, JSON]]:
        if config is None:
            config = self._json
        value = config
        for path_component in self.unpack_path(path):
            if path_component == PATH_PARENT_COMPONENT:
                value = value.parent
            elif (value := value.get(path_component)) is None:
                return None
        return value

    def unpack_path(self, path: str) -> List[str]:
        path_components = []
        for path_component in path.split(self._path_separator):
            if (path_component := path_component.strip()):
                path_components.append(path_component)
        return path_components

    def repack_path(self, path_components: List[str]) -> List[str]:
        return self._path_separator.join(path_components)

    def normalize_path(self, path: str) -> List[str]:
        return self.repack_path(self.unpack_path(path))


with io.open(DEFAULT_CONFIG_FILE, "r") as f:
    config = JSON(json.load(f))
with io.open(DEFAULT_SECRETS_FILE, "r") as f:
    secrets = JSON(json.load(f))

config = Config(config)
secrets = Config(secrets)

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
