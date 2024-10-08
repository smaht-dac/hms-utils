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
    _TYPE_NAME_LENGTH_STR = len(_TYPE_NAME_STR)
    _TYPE_NAME_LENGTH_INT = len(_TYPE_NAME_INT)
    _TYPE_NAME_LENGTH_FLOAT = len(_TYPE_NAME_FLOAT)
    _TYPE_NAME_LENGTH_BOOL = len(_TYPE_NAME_BOOL)

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
        return JSON(data, rvalue=ConfigWithSecrets._secrets_encoded if self._secrets else None)

    def data(self, sorted: bool = True, show: Optional[bool] = False) -> JSON:
        if self._secrets:
            if show is True:
                data = JSON(self._json, rvalue=ConfigWithSecrets._secrets_plaintext)
            elif show is False:
                data = JSON(self._json, rvalue=self._secrets_obfuscated)
            else:
                data = self._json
            return data.sorted() if sorted is True else data
        return super().data(sorted=sorted)

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
                    return value.copy(rvalue=ConfigWithSecrets._secrets_plaintext)
                    # return JSON(value, rvalue=ConfigWithSecrets._secrets_plaintext)
                else:
                    return ConfigWithSecrets._secrets_plaintext(value)
            elif show is False:
                if isinstance(value, JSON):
                    return value.copy(rvalue=self._secrets_obfuscated)
                    # return JSON(value, rvalue=self._secrets_obfuscated)
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

    @staticmethod
    def _secrets_encoded(value: primitive_type) -> str:
        if not is_primitive_type(value):
            return ""
        if (value_type := type(value).__name__) != ConfigWithSecrets._TYPE_NAME_STR:
            return f"{ConfigWithSecrets._SECRET_VALUE_START}{value_type}:{value}{ConfigWithSecrets._SECRET_VALUE_END}"
        secrets_encoded = ""
        start = 0
        while True:
            if not (match := ConfigBasic._MACRO_PATTERN.search(value[start:])):
                # secrets_encoded += value[start:]
                if secret_part := value[start:]:
                    secrets_encoded += (
                        f"{ConfigWithSecrets._SECRET_VALUE_START}str:"
                        f"{secret_part}{ConfigWithSecrets._SECRET_VALUE_END}")
                break
            match_start = match.start()
            match_end = match.end()
            macro_part = value[start + match_start:start + match_end]
            if secret_part := value[start:start + match_start]:
                secrets_encoded += (
                    f"{ConfigWithSecrets._SECRET_VALUE_START}str:"
                    f"{secret_part}{ConfigWithSecrets._SECRET_VALUE_END}")
            secrets_encoded += macro_part
            start += match_end
        return secrets_encoded

    @staticmethod
    def _secrets_plaintext(secrets_encoded: Any, plaintext_value: Optional[Callable] = None) -> primitive_type:
        if (not isinstance(secrets_encoded, str)) or (not secrets_encoded):
            return secrets_encoded
        if not callable(plaintext_value):
            plaintext_value = None
        secret_value_typed = None
        while True:
            if (start := secrets_encoded.find(ConfigWithSecrets._SECRET_VALUE_START)) < 0:
                break
            if (end := secrets_encoded.find(ConfigWithSecrets._SECRET_VALUE_END)) < start:
                break
            secret_value = secrets_encoded[start + ConfigWithSecrets._SECRET_VALUE_START_LENGTH:end]
            if secret_value.startswith(f"{ConfigWithSecrets._TYPE_NAME_STR}:"):
                secret_value = secret_value[ConfigWithSecrets._TYPE_NAME_LENGTH_STR + 1:]
            elif secret_value.startswith(f"{ConfigWithSecrets._TYPE_NAME_INT}:"):
                secret_value = secret_value[ConfigWithSecrets._TYPE_NAME_LENGTH_INT + 1:]
                secret_value_typed = int(secret_value)
            elif secret_value.startswith(f"{ConfigWithSecrets._TYPE_NAME_FLOAT}:"):
                secret_value = secret_value[ConfigWithSecrets._TYPE_NAME_LENGTH_FLOAT + 1:]
                secret_value_typed = float(secret_value)
            elif secret_value.startswith(f"{ConfigWithSecrets._TYPE_NAME_BOOL}:"):
                secret_value = secret_value[ConfigWithSecrets._TYPE_NAME_LENGTH_BOOL + 1:]
                secret_value_typed = True if (secret_value.lower() == "true") else False
            if callable(plaintext_value):
                secret_value = plaintext_value(secret_value)
            secrets_encoded = (
                secrets_encoded[0:start] + secret_value +
                secrets_encoded[end + ConfigWithSecrets._SECRET_VALUE_END_LENGTH:])
        if (secret_value_typed is not None) and (str(secret_value_typed) == secret_value):
            return secret_value_typed
        return secrets_encoded

    def _secrets_obfuscated(self, secrets_encoded: str, obfuscated_value: Optional[Union[str, Callable]] = None) -> str:
        if (not isinstance(secrets_encoded, str)) or (not secrets_encoded):
            return ""
        if not (callable(obfuscated_value) or ((isinstance(obfuscated_value, str)) and obfuscated_value)):
            obfuscated_value = self._obfuscated_value
        while True:
            if (start := secrets_encoded.find(ConfigWithSecrets._SECRET_VALUE_START)) < 0:
                break
            if (end := secrets_encoded.find(ConfigWithSecrets._SECRET_VALUE_END)) < start:
                break
            if callable(obfuscated_value):
                obfuscated = (obfuscated_value(self._obfuscated_value)
                              if end > start + ConfigWithSecrets._SECRET_VALUE_START_LENGTH else "")
            else:
                obfuscated = obfuscated_value if end > start + ConfigWithSecrets._SECRET_VALUE_START_LENGTH else ""
            secrets_encoded = (
                secrets_encoded[0:start] + obfuscated +
                secrets_encoded[end + ConfigWithSecrets._SECRET_VALUE_END_LENGTH:])
        return secrets_encoded

    def _contains_secrets(self, secrets_encoded: Any) -> bool:
        if not isinstance(secrets_encoded, str):
            return False
        if (start := secrets_encoded.find(ConfigWithSecrets._SECRET_VALUE_START)) < 0:
            return False
        if secrets_encoded.find(ConfigWithSecrets._SECRET_VALUE_END) < start:
            return False
        return True

    def _dump_for_testing(self, sorted: bool = False,
                          verbose: bool = False, check: bool = False, show: bool = False) -> None:
        self.data(show=show, sorted=sorted)._dump_for_testing(verbose=verbose, check=check)
