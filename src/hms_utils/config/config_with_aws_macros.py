from __future__ import annotations
from boto3 import client as BotoClient
import json
import re
from typing import Any, Callable, Optional
from hms_utils.config.config_basic import ConfigBasic
from hms_utils.dictionary_parented import JSON
from hms_utils.config.config_with_secrets import ConfigWithSecrets
from hms_utils.env_utils import os_environ


class ConfigWithAwsMacros(ConfigBasic):

    _AWS_SECRET_MACRO_NAME_PREFIX = "aws-secret:"
    _AWS_SECRET_MACRO_START = f"{ConfigBasic._MACRO_START}{_AWS_SECRET_MACRO_NAME_PREFIX}"
    _AWS_SECRET_MACRO_END = ConfigBasic._MACRO_END
    _AWS_SECRET_MACRO_PATTERN = re.compile(r"\$\{aws-secret:([^}]+)\}")
    _AWS_SECRET_NAME_NAME = "IDENTITY"
    _AWS_PROFILE_ENV_NAME = "AWS_PROFILE"

    def __init__(self, config: JSON,
                 name: Optional[str] = None,
                 path_separator: Optional[str] = None,
                 custom_macro_lookup: Optional[Callable] = None,
                 raise_exception: bool = False,
                 aws_secrets_name: Optional[str] = None,
                 noaws: bool = False,
                 debug: bool = False, **kwargs) -> None:
        self._aws_secrets_name = aws_secrets_name.strip() if isinstance(aws_secrets_name, str) else None
        self._noaws = noaws is True
        self._raise_exception = raise_exception is True
        self._debug = debug is True
        super().__init__(config,
                         name=name,
                         path_separator=path_separator,
                         custom_macro_lookup=self._lookup_macro_custom,
                         raise_exception=raise_exception, **kwargs)

    @property
    def aws_secrets_name(self) -> Optional[str]:
        return self._aws_secrets_name

    @aws_secrets_name.setter
    def aws_secrets_name(self, value: str) -> Optional[str]:
        self._aws_secrets_name = value.strip() if isinstance(value, str) else None

    def _lookup_macro_custom(self, macro_value: str, context: Optional[JSON] = None) -> Any:
        if not macro_value.startswith(ConfigWithAwsMacros._AWS_SECRET_MACRO_NAME_PREFIX):
            return None
        secret_specifier = macro_value[len(ConfigWithAwsMacros._AWS_SECRET_MACRO_NAME_PREFIX):]
        return self._lookup_aws_secret(secret_specifier, context)

    def _lookup_aws_secret(self, secret_specifier: str, context: Optional[JSON] = None) -> Optional[str]:
        def lookup_aws_profile_environment_variable(context: Optional[JSON] = None) -> Optional[str]:
            if isinstance(context, JSON):
                while True:
                    if aws_profile := context.get(ConfigWithAwsMacros._AWS_PROFILE_ENV_NAME):
                        return aws_profile
                    if not (context := context.parent):
                        break
            return None
        if (index := secret_specifier.find(self._path_separator)) > 0:
            secret_name = secret_specifier[index + 1:]
            secrets_name = secret_specifier[0:index]
        else:
            secret_name = secret_specifier
            if self._aws_secrets_name:
                secrets_name = self._aws_secrets_name
            else:
                secrets_name = super().lookup(ConfigWithAwsMacros._AWS_PROFILE_ENV_NAME, context=context)
        if not (secret_name and secrets_name):
            return None
        if aws_profile := lookup_aws_profile_environment_variable(context):
            with os_environ(ConfigWithAwsMacros._AWS_PROFILE_ENV_NAME, aws_profile):
                return self._aws_get_secret(secrets_name, secret_name, aws_profile)
        return self._aws_get_secret(secrets_name, secret_name, aws_profile)

    def _aws_get_secret(self, secrets_name: str, secret_name: str, aws_profile: Optional[str] = None) -> Optional[str]:
        if self._noaws:
            return None
        try:
            boto_secrets = BotoClient("secretsmanager")
            if self._debug:
                print(f"DEBUG: Reading AWS secrets: {secrets_name}/{secret_name}")
            secrets = boto_secrets.get_secret_value(SecretId=secrets_name)
            secrets = json.loads(secrets.get("SecretString"))
            if ((value := secrets[secret_name]) is not None) and isinstance(self, ConfigWithSecrets):
                value = ConfigWithSecrets._secrets_encoded(value)
            return value
        except Exception as e:
            if self._raise_exception is True:
                raise e
            self._warning(f"Cannot find AWS secret: {secrets_name}/{secret_name}"
                          f"{f' (profile: {aws_profile} if aws_profile else '''}")
        return None

    def _contains_aws_secrets(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        if (start := value.find(ConfigWithAwsMacros._AWS_SECRET_MACRO_START)) < 0:
            return False
        if value.find(ConfigWithAwsMacros._AWS_SECRET_MACRO_END) < start:
            return False
        return True

    def _note_macro_not_found(self, macro_value: str) -> None:
        if not macro_value.startswith(ConfigWithAwsMacros._AWS_SECRET_MACRO_NAME_PREFIX):
            super()._note_macro_not_found(macro_value)
