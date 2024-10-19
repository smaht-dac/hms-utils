from __future__ import annotations
from boto3 import client as BotoClient
from functools import lru_cache
import json
import os
import re
from typing import Any, Callable, Optional, Tuple
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
    _AWS_CACHED_ACCOUNT_NUMBERS = {}
    _TYPE_NAME_AWS = "aws"

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
            nonlocal self
            if aws_profile := self.lookup(name, context=context, show=True):
                return aws_profile
            return os.environ.get(name)
            if isinstance(context, JSON):
                while True:
                    if aws_profile := context.get(name):
                        return aws_profile
                    if not (context := context.parent):
                        break
            return os.environ.get(name)
        if (index := secret_specifier.find(self._path_separator)) > 0:
            secret_name = secret_specifier[index + 1:]
            secrets_name = secret_specifier[0:index]
        else:
            secret_name = secret_specifier
            if self._aws_secrets_name:
                secrets_name = self._aws_secrets_name
            else:
                secrets_name = lookup_environment_variable(ConfigWithAwsMacros._AWS_SECRET_NAME_NAME, context)
        if not (secret_name and secrets_name):
            return None
        if aws_profile := lookup_environment_variable(ConfigWithAwsMacros._AWS_PROFILE_ENV_NAME, context):
            with os_environ(ConfigWithAwsMacros._AWS_PROFILE_ENV_NAME, aws_profile):
                return self._aws_get_secret(secrets_name, secret_name, aws_profile)
        return self._aws_get_secret(secrets_name, secret_name, aws_profile)

    def _aws_get_secret(self, secrets_name: str, secret_name: str, aws_profile: Optional[str]) -> Optional[str]:
        if self._noaws:
            return None
        value, account_number = self._aws_read_secret(secrets_name, secret_name, aws_profile)
        if value is not None:
            if isinstance(self, ConfigWithSecrets) and self.secrets:
                # See: ConfigWithAwsMacros._secrets_plaintext_value
                value = self._secrets_encoded(
                    f"{account_number}{ConfigWithSecrets._TYPE_NAME_SEPARATOR}"
                    f"{secrets_name}{ConfigWithSecrets._TYPE_NAME_SEPARATOR}"
                    f"{secret_name}{ConfigWithSecrets._TYPE_NAME_SEPARATOR}{value}",
                    value_type=ConfigWithAwsMacros._TYPE_NAME_AWS)
        return value

    @lru_cache
    def _aws_read_secret(self, secrets_name: str, secret_name: str,
                         aws_profile: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        try:
            self._debug(f"Reading AWS secret {secrets_name}/{secret_name}"
                        f"{f' {chars.dot} profile: {aws_profile}' if aws_profile else ''}")
            secrets, account_number = self._aws_read_secrets(secrets_name, aws_profile)
            if (not secrets) or ((value := secrets.get(secret_name)) is None):
                self._warning(f"Cannot find AWS secret {secrets_name}/{secret_name}"
                              f"{f' {chars.dot} profile: {aws_profile}' if aws_profile else ''}")
                return None, None
            self._debug(f"Read AWS secret OK: {secrets_name}/{secret_name}"
                        f"{f' {chars.dot} profile: {aws_profile}' if aws_profile else ''}")
            return value, account_number
        except Exception as e:
            if self._raise_exception is True:
                raise e
            msg = self._aws_error_message(f"Cannot read AWS secret {secrets_name}/{secret_name}", aws_profile, e)
            self._debug(msg)
            self._warning(msg)
            return None, None

    @lru_cache
    def _aws_read_secrets(self, secrets_name: str, aws_profile: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        def extract_aws_account_number(secrets: dict) -> str:
            try:
                return secrets["ARN"].split(':')[4].strip()
            except Exception:
                return ""
        try:
            self._debug(f"Reading AWS secrets {secrets_name}"
                        f"{f' {chars.dot} profile: {aws_profile}' if aws_profile else ''}")
            boto_secrets = ConfigWithAwsMacros._boto_client("secretsmanager")
            secrets = boto_secrets.get_secret_value(SecretId=secrets_name)
            account_number = extract_aws_account_number(secrets)
            secrets = json.loads(secrets.get("SecretString"))
            self._debug(lambda: self._aws_error_message(f"Read AWS secrets OK: {secrets_name}", aws_profile))
            return secrets, account_number
        except Exception as e:
            if self._raise_exception is True:
                raise e
            msg = self._aws_error_message(f"Cannot read AWS secrets {secrets_name}", aws_profile, e)
            self._debug(msg)
            self._warning(msg)
            return None, None

    def _aws_error_message(self, message: str, aws_profile: Optional[str],
                           exception: Optional[Exception] = None, _noprofile: bool = False) -> str:
        if _noprofile is not True:
            if aws_profile:
                message += f" {chars.dot} profile: {aws_profile}"
            if aws_account_number := self._aws_current_account_number(aws_profile):
                message += f" {chars.dot} account: {aws_account_number}"
            elif not aws_profile:
                message += f" {chars.dot} profile: unspecified"
        if exception := str(exception):
            if ("token" in exception) and ("expired" in exception):
                message += f" {chars.dot} expired"
            elif ("not" in exception) and ("found" in exception):
                message += f" {chars.dot} unknown"
        return message

    @lru_cache
    def _aws_current_account_number(self, aws_profile: Optional[str]) -> Optional[str]:
        try:
            self._debug(f"Reading AWS account number{f': {aws_profile}' if aws_profile else ''}")
            aws_account_number = self._boto_client("sts").get_caller_identity()["Account"]
            self._debug(f"Read AWS account number OK{f': {aws_profile}' if aws_profile else ''}")
            return aws_account_number
        except Exception as e:
            msg = self._aws_error_message(
                f"Cannot read AWS account number{f': {aws_profile}' if aws_profile else ''}",
                aws_profile, e, _noprofile=True)
            self._debug(msg)
            return None

    def _contains_aws_secret_values(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        if (start := value.find(ConfigWithSecrets._SECRET_VALUE_START + ConfigWithAwsMacros._TYPE_NAME_AWS)) < 0:
            return False
        return value.find(ConfigWithSecrets._SECRET_VALUE_END) > start

    def _secrets_plaintext_value(self, value: str) -> Optional[str]:
        # See: ConfigWithAwsMacros._aws_get_secret
        if (value.startswith(ConfigWithAwsMacros._TYPE_NAME_AWS) and
            (len(value_parts := value.split(ConfigWithSecrets._TYPE_NAME_SEPARATOR)) >= 5)):  # noqa
            return ConfigWithSecrets._TYPE_NAME_SEPARATOR.join(value_parts[4:])
        return None

    def _secrets_plaintext_info(self, value: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        if (value.startswith(ConfigWithSecrets._SECRET_VALUE_START) and
            value.endswith(ConfigWithSecrets._SECRET_VALUE_END)):  # noqa
            value = value[ConfigWithSecrets._SECRET_VALUE_START_LENGTH:-ConfigWithSecrets._SECRET_VALUE_END_LENGTH]
            if ((len(secrets_encoded_parts := value.split(ConfigWithSecrets._TYPE_NAME_SEPARATOR)) >= 5) and
                secrets_encoded_parts[4]):  # noqa
                if ((aws_account_number := secrets_encoded_parts[1]) and
                    (aws_secrets_name := secrets_encoded_parts[2]) and
                    (aws_secret_name := secrets_encoded_parts[3])):  # noqa
                    return aws_account_number, aws_secrets_name, aws_secret_name
        return None, None, None

    def _note_macro_not_found(self, macro_value: str,
                              context: Optional[JSON] = JSON, context_path: Optional[str] = None) -> None:
        if not macro_value.startswith(ConfigWithAwsMacros._AWS_SECRET_MACRO_NAME_PREFIX):
            super()._note_macro_not_found(macro_value, context, context_path=context_path)

    @staticmethod
    def _boto_client(service: str) -> object:
        # This boto3.DEFAULT_SESSION works around an oddity discovered way back (circa 2022-06-19) with the
        # boto3 session getting stuck/cached or something once used once and then again with a different profile.
        # https://hms-dbmi.slack.com/archives/D03ENS13XA7/p1655648553779689
        import boto3
        boto3.DEFAULT_SESSION = None
        return BotoClient(service)
