from __future__ import annotations
from boto3 import client as BotoClient
import json
import re
from typing import Any, Callable, Optional, Union
from hms_utils.config.hms_config import Config
from hms_utils.dictionary_utils import JSON


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


config = Config({
    "abc": {
        "def": "def_value"
    },
    "ghi": {
        "jk": "jk_value"
    }
})

x = config.lookup("ghi/abc/def", inherit_simple=False)
print(x)
