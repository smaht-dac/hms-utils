from __future__ import annotations
import os
from typing import Any, Callable, List, Optional, Tuple, Union
from hms_utils.dictionary_parented import DictionaryParented as JSON
from hms_utils.type_utils import is_primitive_type, primitive_type
from hms_utils.config.config_basic import ConfigBasic


class ConfigWithSecrets(ConfigBasic):

    _SECRET_OBFUSCATED_VALUE = "********"
    _SECRET_VALUE_START = "@@@@@@@__mark_secret_start__["
    _SECRET_VALUE_END = "]__mark_secret_end__@@@@@@@"
    _SECRET_VALUE_START_LENGTH = len(_SECRET_VALUE_START)
    _SECRET_VALUE_END_LENGTH = len(_SECRET_VALUE_END)
    _TYPE_NAME_STR = type("").__name__
    _TYPE_NAME_INT = type(1).__name__
    _TYPE_NAME_FLOAT = type(1.0).__name__
    _TYPE_NAME_BOOL = type(True).__name__
    _TYPE_NAME_SEPARATOR = ":"
    _TYPE_NAME_LENGTH_STR = len(_TYPE_NAME_STR)
    _TYPE_NAME_LENGTH_INT = len(_TYPE_NAME_INT)
    _TYPE_NAME_LENGTH_FLOAT = len(_TYPE_NAME_FLOAT)
    _TYPE_NAME_LENGTH_BOOL = len(_TYPE_NAME_BOOL)
    _TYPE_NAME_LENGTH_SEPARATOR = len(_TYPE_NAME_SEPARATOR)

    def __init__(self, config: Union[dict, str],
                 name: Optional[str] = None,
                 path_separator: Optional[str] = None,
                 custom_macro_lookup: Optional[Callable] = None,
                 raise_exception: bool = False,
                 secrets: bool = False,
                 obfuscated_value: Optional[str] = None, **kwargs) -> None:
        self._secrets = (secrets is True) or (isinstance(config, str) and ("secret" in os.path.basename(config)))
        self._obfuscated_value = (obfuscated_value
                                  if isinstance(obfuscated_value, str) and obfuscated_value
                                  else ConfigWithSecrets._SECRET_OBFUSCATED_VALUE)
        super().__init__(config=config,
                         name=name,
                         path_separator=path_separator,
                         custom_macro_lookup=custom_macro_lookup,
                         raise_exception=raise_exception, **kwargs)

    def _create_json(self, data: dict) -> JSON:
        if not self._secrets:
            return super()._create_json(data)
        return JSON(data, rvalue=self._secrets_encoded if self._secrets else None)

    def data(self, show: Optional[bool] = False) -> JSON:
        if self._secrets:
            if show is True:
                return JSON(self.json, rvalue=self._secrets_plaintext).sorted()
            elif show is False:
                return JSON(self.json, rvalue=self._secrets_obfuscated).sorted()
        return super().data()

    @property
    def secrets(self) -> bool:
        return self._secrets

    def lookup(self, path: str,
               context: Optional[JSON] = None,
               noexpand: bool = False,
               inherit_simple: bool = False,
               inherit_none: bool = False,
               show: Optional[bool] = False) -> Optional[Union[Any, JSON]]:
        value = super().lookup(path=path, context=context,
                               noexpand=noexpand, inherit_simple=inherit_simple, inherit_none=inherit_none, show=show)
        if self._secrets:
            if value is None:
                return value
            elif show is True:
                if isinstance(value, JSON):
                    return value.duplicate(rvalue=self._secrets_plaintext)
                else:
                    return self._secrets_plaintext(value)
            elif show is False:
                if isinstance(value, JSON):
                    return value.duplicate(rvalue=self._secrets_obfuscated)
                else:
                    return self._secrets_obfuscated(value)
        return value

    def merge(self, data: Union[Union[dict, ConfigBasic],
                                List[Union[dict, ConfigBasic]]]) -> Tuple[List[str], List[str]]:
        if isinstance(data, ConfigWithSecrets):
            self._secrets = data._secrets
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, ConfigWithSecrets):
                    self._secrets = self._secrets or item._secrets
        return super().merge(data)

    # All of this marking of secrets stuff is just so that when obtaining values (for lookup/print/dump/display),
    # any strings which came from a "secret" configuration can be obfuscated by default, or shown if desired;
    # we do go to the trouble of not marking macros within secret config values as secret.

    def _secrets_encoded(self, value: primitive_type, value_type: Optional[str] = None) -> str:
        if not is_primitive_type(value):
            return ""
        if (actual_value_type := type(value).__name__) != ConfigWithSecrets._TYPE_NAME_STR:
            return (f"{ConfigWithSecrets._SECRET_VALUE_START}{actual_value_type}"
                    f"{ConfigWithSecrets._TYPE_NAME_SEPARATOR}{value}{ConfigWithSecrets._SECRET_VALUE_END}")
        if not (isinstance(value_type, str) and value_type):
            value_type = ConfigWithSecrets._TYPE_NAME_STR
        secrets_encoded = ""
        start = 0
        while True:
            if not (match := ConfigBasic._MACRO_PATTERN.search(value[start:])):
                if secret_part := value[start:]:
                    secrets_encoded += (
                        f"{ConfigWithSecrets._SECRET_VALUE_START}{value_type}"
                        f"{ConfigWithSecrets._TYPE_NAME_SEPARATOR}{secret_part}{ConfigWithSecrets._SECRET_VALUE_END}")
                break
            match_start = match.start()
            match_end = match.end()
            macro_part = value[start + match_start:start + match_end]
            if secret_part := value[start:start + match_start]:
                secrets_encoded += (
                    f"{ConfigWithSecrets._SECRET_VALUE_START}{value_type}"
                    f"{ConfigWithSecrets._TYPE_NAME_SEPARATOR}{secret_part}{ConfigWithSecrets._SECRET_VALUE_END}")
            secrets_encoded += macro_part
            start += match_end
        return secrets_encoded

    def _secrets_plaintext(self, value: Any, plaintext_value: Optional[Callable] = None) -> Any:
        if not callable(plaintext_value):
            plaintext_value = None
        if (not isinstance(value, str)) or (not value):
            if isinstance(value, dict):
                json = isinstance(value, JSON)
                value = {k: self._secrets_plaintext(v, plaintext_value=plaintext_value) for k, v in value.items()}
                return JSON(value) if json else value
            elif isinstance(value, list):
                return [self._secrets_plaintext(e, plaintext_value=plaintext_value) for e in value]
            return value
        secret_value_typed = None
        while True:
            if (start := value.find(ConfigWithSecrets._SECRET_VALUE_START)) < 0:
                break
            if (end := value.find(ConfigWithSecrets._SECRET_VALUE_END)) < start:
                break
            secret_value = value[start + ConfigWithSecrets._SECRET_VALUE_START_LENGTH:end]
            secret_value, secret_value_typed = self._secrets_plaintext_value(secret_value)
            if plaintext_value:
                secret_value = plaintext_value(secret_value)
            value = value[0:start] + secret_value + value[end + ConfigWithSecrets._SECRET_VALUE_END_LENGTH:]
        if (secret_value_typed is not None) and (str(secret_value_typed) == secret_value):
            return secret_value_typed
        return value

    def _secrets_plaintext_value(self, value: str) -> Tuple[primitive_type, Any]:
        from hms_utils.config.config_with_aws_macros import ConfigWithAwsMacros  # here to avoid circular imports
        value_typed = None
        if value.startswith(f"{ConfigWithSecrets._TYPE_NAME_STR}{ConfigWithSecrets._TYPE_NAME_SEPARATOR}"):
            value = value[ConfigWithSecrets._TYPE_NAME_LENGTH_STR + ConfigWithSecrets._TYPE_NAME_LENGTH_SEPARATOR:]
        elif value.startswith(f"{ConfigWithSecrets._TYPE_NAME_INT}{ConfigWithSecrets._TYPE_NAME_SEPARATOR}"):
            value = value[ConfigWithSecrets._TYPE_NAME_LENGTH_INT + ConfigWithSecrets._TYPE_NAME_LENGTH_SEPARATOR:]
            value_typed = int(value)
        elif value.startswith(f"{ConfigWithSecrets._TYPE_NAME_FLOAT}{ConfigWithSecrets._TYPE_NAME_SEPARATOR}"):
            value = value[ConfigWithSecrets._TYPE_NAME_LENGTH_FLOAT + ConfigWithSecrets._TYPE_NAME_LENGTH_SEPARATOR:]
            value_typed = float(value)
        elif value.startswith(f"{ConfigWithSecrets._TYPE_NAME_BOOL}{ConfigWithSecrets._TYPE_NAME_SEPARATOR}"):
            value = value[ConfigWithSecrets._TYPE_NAME_LENGTH_BOOL + ConfigWithSecrets._TYPE_NAME_LENGTH_SEPARATOR:]
            value_typed = True if (value.lower() == "true") else False
        elif isinstance(self, ConfigWithAwsMacros):
            if (aws_value := ConfigWithAwsMacros._secrets_plaintext_value(self, value)) is not None:
                value = aws_value
        return value, value_typed

    def _secrets_obfuscated(self, value: Any, obfuscated_value: Optional[Union[str, Callable]] = None) -> Any:
        if (not isinstance(value, str)) or (not value):
            if isinstance(value, dict):
                json = isinstance(value, JSON)
                value = {k: self._secrets_obfuscated(v, obfuscated_value=obfuscated_value) for k, v in value.items()}
                return JSON(value) if json else value
            elif isinstance(value, list):
                return [self._secrets_obfuscated(e, obfuscated_value=obfuscated_value) for e in value]
            return value
        if not (callable(obfuscated_value) or ((isinstance(obfuscated_value, str)) and obfuscated_value)):
            obfuscated_value = self._obfuscated_value
        while True:
            if (start := value.find(ConfigWithSecrets._SECRET_VALUE_START)) < 0:
                break
            if (end := value.find(ConfigWithSecrets._SECRET_VALUE_END)) < start:
                break
            if callable(obfuscated_value):
                obfuscated = (obfuscated_value(self._obfuscated_value)
                              if end > start + ConfigWithSecrets._SECRET_VALUE_START_LENGTH else "")
            else:
                obfuscated = obfuscated_value if end > start + ConfigWithSecrets._SECRET_VALUE_START_LENGTH else ""
            value = value[0:start] + obfuscated + value[end + ConfigWithSecrets._SECRET_VALUE_END_LENGTH:]
        return value

    def _contains_secret_values(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        if (start := value.find(ConfigWithSecrets._SECRET_VALUE_START)) < 0:
            return False
        return value.find(ConfigWithSecrets._SECRET_VALUE_END) > start
