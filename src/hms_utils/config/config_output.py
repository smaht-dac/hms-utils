from __future__ import annotations
from typing import Any, Optional
from hms_utils.chars import chars
from hms_utils.dictionary_utils import print_dictionary_list, print_dictionary_tree
from hms_utils.config.config import Config
from hms_utils.terminal_utils import terminal_color


class ConfigOutput:

    @staticmethod
    def print_tree(config: Config, show: bool = False, raw: bool = False, nocolor: bool = False) -> None:
        def value_modifier(path: str, value: Any) -> Optional[str]:
            nonlocal config
            if raw is not True:
                value = config.lookup(path, show=None)
            return ConfigOutput._display_value(config, value=value, show=show, nocolor=nocolor)
        def tree_arrow_indicator(path: str, value: Any) -> Optional[str]:  # noqa
            nonlocal config, nocolor
            if config._contains_secrets(value):
                return chars.rarrow if nocolor is True else terminal_color(chars.rarrow, "red")
            return None
        print_dictionary_tree(config.data(show=None),
                              value_modifier=value_modifier, arrow_indicator=tree_arrow_indicator)

    @staticmethod
    def print_list(config: Config, show: bool = False, raw: bool = False, nocolor: bool = False) -> None:
        def value_modifier(path: str, value: Any) -> Optional[str]:
            nonlocal config, nocolor
            if raw is not True:
                return config.lookup(path, show=show)
            return ConfigOutput._display_value(config, value=value, show=show, nocolor=nocolor)
        print_dictionary_list(config.data(show=None), value_modifier=value_modifier)

    @staticmethod
    def _display_value(config: Config, value: Any, show: bool, nocolor: bool = False) -> Optional[str]:
        def display_secret_value(value: Any) -> str:
            nonlocal nocolor
            return str(value) if nocolor is True else terminal_color(str(value), "red")
        if show is True:
            return config._secrets_plaintext(value, plaintext_value=display_secret_value)
        return config._secrets_obfuscated(value, obfuscated_value=display_secret_value)
