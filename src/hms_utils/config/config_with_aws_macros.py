from __future__ import annotations
from boto3 import client as BotoClient
import json
import re
from typing import Any, Callable, Optional, Union
from hms_utils.config.config_basic import ConfigBasic
from hms_utils.dictionary_utils import JSON


class ConfigWithAwsMacros(ConfigBasic):

    _AWS_SECRET_MACRO_NAME_PREFIX = "aws-secret:"
    _AWS_SECRET_MACRO_START = f"{ConfigBasic._MACRO_START}{_AWS_SECRET_MACRO_NAME_PREFIX}"
    _AWS_SECRET_MACRO_END = ConfigBasic._MACRO_END
    _AWS_SECRET_MACRO_PATTERN = re.compile(r"\$\{aws-secret:([^}]+)\}")
    _AWS_SECRET_NAME_NAME = "IDENTITY"

    def __init__(self, config: JSON,
                 name: Optional[str] = None,
                 path_separator: Optional[str] = None,
                 custom_macro_lookup: Optional[Callable] = None,
                 warning: Optional[Union[Callable, bool]] = None,
                 raise_exception: bool = False,
                 noaws: bool = False, **kwargs) -> None:

        super().__init__(config,
                         name=name,
                         path_separator=path_separator,
                         custom_macro_lookup=self._lookup_macro_custom,
                         warning=warning,
                         raise_exception=raise_exception, **kwargs)

        self._noaws = noaws is True
        self._raise_exception = raise_exception is True

    def _lookup_macro_custom(self, macro_value: str, context: Optional[JSON] = None) -> Any:
        if not macro_value.startswith(ConfigWithAwsMacros._AWS_SECRET_MACRO_NAME_PREFIX):
            return None
        secret_specifier = macro_value[len(ConfigWithAwsMacros._AWS_SECRET_MACRO_NAME_PREFIX):]
        return self._lookup_aws_secret(secret_specifier, context)

    def _lookup_aws_secret(self, secret_specifier: str, context: str) -> Optional[str]:
        if (index := secret_specifier.find(self._path_separator)) > 0:
            secret_name = secret_specifier[index + 1:]
            secrets_name = secret_specifier[0:index]
        else:
            secret_name = secret_specifier
            secrets_name = self.lookup(ConfigWithAwsMacros._AWS_SECRET_NAME_NAME, context)
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
