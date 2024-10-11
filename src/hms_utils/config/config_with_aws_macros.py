from __future__ import annotations
from boto3 import client as BotoClient
from functools import lru_cache
import json
import re
from typing import Any, Callable, Optional
from hms_utils.config.config_basic import ConfigBasic
from hms_utils.dictionary_parented import JSON
from hms_utils.chars import chars
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
                 noaws: bool = False, **kwargs) -> None:
        self._aws_secrets_name = aws_secrets_name.strip() if isinstance(aws_secrets_name, str) else None
        self._noaws = noaws is True
        self._raise_exception = raise_exception is True
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
        def lookup_environment_variable(name: str, context: Optional[JSON] = None) -> Optional[str]:
            if isinstance(context, JSON):
                while True:
                    if aws_profile := context.get(name):
                        return aws_profile
                    if not (context := context.parent):
                        break
            return None
        def lookup_aws_profile_environment_variable(context: Optional[JSON] = None) -> Optional[str]:  # noqa
            return lookup_environment_variable(ConfigWithAwsMacros._AWS_PROFILE_ENV_NAME, context)
        def lookup_identity_environment_variable(context: Optional[JSON] = None) -> Optional[str]:  # noqa
            return lookup_environment_variable(ConfigWithAwsMacros._AWS_SECRET_NAME_NAME, context)
        if (index := secret_specifier.find(self._path_separator)) > 0:
            secret_name = secret_specifier[index + 1:]
            secrets_name = secret_specifier[0:index]
        else:
            secret_name = secret_specifier
            if self._aws_secrets_name:
                secrets_name = self._aws_secrets_name
            else:
                secrets_name = lookup_identity_environment_variable(context)
        if not (secret_name and secrets_name):
            return None
        if aws_profile := lookup_aws_profile_environment_variable(context):
            with os_environ(ConfigWithAwsMacros._AWS_PROFILE_ENV_NAME, aws_profile):
                return self._aws_get_secret(secrets_name, secret_name, aws_profile)
        return self._aws_get_secret(secrets_name, secret_name, aws_profile)

    @lru_cache
    def _aws_get_secret(self, secrets_name: str, secret_name: str, aws_profile: Optional[str] = None) -> Optional[str]:
        if self._noaws:
            return None
        try:
            boto_secrets = BotoClient("secretsmanager")
            self._debug(f"DEBUG: Reading AWS secret: {secrets_name}/{secret_name}"
                        f"{f' (profile: {aws_profile})' if aws_profile else ''}")
            secrets = boto_secrets.get_secret_value(SecretId=secrets_name)
            secrets = json.loads(secrets.get("SecretString"))
        except Exception as e:
            if self._raise_exception is True:
                raise e
            message = f"Cannot read AWS secrets: {secrets_name}"
            if aws_profile:
                message += f" {chars.dot} profile: {aws_profile}"
            if ("token" in str(e)) and ("expired" in str(e)):
                message += f" {chars.dot} expired"
            self._warning(message)
            return None
        if (value := secrets.get(secret_name)) is None:
            self._warning(f"Cannot find AWS secret: {secrets_name}/{secret_name}"
                          f"{f' {chars.dot} profile: {aws_profile}' if aws_profile else ''}")
            return None
        if isinstance(self, ConfigWithSecrets):
            value = ConfigWithSecrets._secrets_encoded(value)
        return value

    def _contains_aws_secrets(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        if (start := value.find(ConfigWithAwsMacros._AWS_SECRET_MACRO_START)) < 0:
            return False
        if value.find(ConfigWithAwsMacros._AWS_SECRET_MACRO_END) < start:
            return False
        return True

    def _note_macro_not_found(self, macro_value: str, context: Optional[JSON] = JSON) -> None:
        if not macro_value.startswith(ConfigWithAwsMacros._AWS_SECRET_MACRO_NAME_PREFIX):
            super()._note_macro_not_found(macro_value, context)
