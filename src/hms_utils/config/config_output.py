from __future__ import annotations
from functools import lru_cache
from typing import Any, Optional
from hms_utils.chars import chars
from hms_utils.dictionary_print_utils import print_dictionary_list, print_dictionary_tree
from hms_utils.config.config import Config
from hms_utils.config.config_with_aws_macros import ConfigWithAwsMacros
from hms_utils.terminal_utils import terminal_color


class ConfigOutput:

    @staticmethod
    def print_tree(config: Config, show: bool = False, raw: bool = False, nocolor: bool = False) -> None:
        def value_modifier(path: str, value: Any) -> Optional[str]:  # noqa
            nonlocal config, show, raw
            if raw is not True:
                value = ConfigOutput._lookup(config, path, show=None)
                if isinstance(config, ConfigWithAwsMacros) and config._contains_aws_secret_values(value):
                    aws_account_number, aws_secrets_name, aws_secret_name = config._secrets_plaintext_info(value)
                    if aws_account_number:
                        value += (f" {chars.dot} {aws_account_number}"
                                  f" {chars.dot_hollow} {aws_secrets_name}/{aws_secret_name}")
                return ConfigOutput._display_value(config, value, show=show, nocolor=nocolor)
            elif show is True:
                return ConfigOutput._lookup(config, path, show=None)
        def tree_arrow_indicator(path: str, value: Any) -> Optional[str]:  # noqa
            nonlocal config, show, raw
            if (raw is not True) or (show is True):
                if config._contains_secret_values(ConfigOutput._lookup(config, path, show=None)):
                    return terminal_color(chars.rarrow, "red", bold=True, nocolor=nocolor)
        print_dictionary_tree(config.data(show=None),
                              value_modifier=value_modifier,
                              arrow_indicator=tree_arrow_indicator, indent=2)

    @staticmethod
    def print_list(config: Config, show: bool = False, raw: bool = False, nocolor: bool = False) -> None:
        def value_modifier(path: str, value: Any) -> Optional[str]:
            nonlocal config, nocolor, show, raw
            if raw is not True:
                value = ConfigOutput._lookup(config, path, show=None)
                aws_account_number = aws_secrets_name = aws_secret_name = None
                if isinstance(config, ConfigWithAwsMacros) and config._contains_aws_secret_values(value):
                    aws_account_number, aws_secrets_name, aws_secret_name = \
                        config._secrets_plaintext_info(value)
                value = ConfigOutput._display_value(config, value, show=show, nocolor=nocolor)
                if aws_account_number:
                    value += (f" {chars.dot} {aws_account_number}"
                              f" {chars.dot_hollow} {aws_secrets_name}/{aws_secret_name}")
            elif show is True:
                value = ConfigOutput._lookup(config, path, show=None)
            return value
        print_dictionary_list(config.data(show=None), value_modifier=value_modifier)

    @staticmethod
    def _display_value(config: Config, value: Any, show: bool, nocolor: bool = False) -> Optional[str]:
        def display_secret_value(value: Any) -> str:
            nonlocal nocolor
            return terminal_color(str(value), "red", bold=True, nocolor=nocolor)
        if show is True:
            return config._secrets_plaintext(value, plaintext_value=display_secret_value)
        elif show is False:
            return config._secrets_obfuscated(value, obfuscated_value=display_secret_value)
        else:
            return value

    @lru_cache
    def _lookup(config: Config, path: str, show: Optional[bool]) -> Any:
        return config.lookup(path, show=show)
