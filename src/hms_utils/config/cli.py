from __future__ import annotations
from boto3 import client as BotoClient
from copy import deepcopy
from functools import lru_cache
import io
import json
import os
import re
import stat
import sys
import traceback
from typing import Any, List, Optional, Tuple, Union
import yaml
from hms_utils.chars import chars
from hms_utils.dictionary_utils import (
    JSON, delete_paths_from_dictionary, print_dictionary_list,
    print_dictionary_tree, sort_dictionary
)
from hms_utils.version_utils import get_version
from hms_utils.terminal_utils import terminal_color as color
from hms_utils.config.hms_config import Config

DEFAULT_CONFIG_DIR = "~/.config/hms"
DEFAULT_CONFIG_FILE_NAME = "config.json"
DEFAULT_SECRETS_FILE_NAME = "secrets.json"
DEFAULT_PATH_SEPARATOR = "/"
DEFAULT_EXPORT_NAME_SEPARATOR = ":"
AWS_PROFILE_ENV_NAME = "AWS_PROFILE"
OBFUSCATED_VALUE = "********"

SUPPRESS_AWS_SECRET_NOT_FOUND_WARNING = False  # Hack


def main():

    args = parse_args(sys.argv[1:])
    sys.exit(0)


def main_show_script_path():
    sys.argv = ["hms-config", "--functions"]
    main()


def parse_args(argv: List[str]) -> object:

    class Args:
        config_file = DEFAULT_CONFIG_FILE_NAME
        secrets_file = DEFAULT_SECRETS_FILE_NAME

    args = Args()

    def get_config_dir() -> str:
        nonlocal argv
        config_dir = os.path.expanduser(DEFAULT_CONFIG_DIR)
        if value := os.environ.get("HMS_CONFIG_DIR"):
            config_dir = value
        argi = 0
        while argi < len(argv):
            arg = argv[argi] ; argi += 1  # noqa
            if arg in ["--dir", "-dir", "--directory", "-directory"]:
                if not ((argi < len(argv)) and (config_dir := argv[argi])):
                    _usage()
                del argv[argi - 1:argi + 1]
                break
        if not os.path.isabs(config_dir):
            config_dir = os.path.normpath(os.path.join(os.getcwd(), config_dir))
        if not os.path.isdir(config_dir := os.path.normpath(config_dir)):
            _error(f"Configuration directory does not exist: {config_dir}")
        return config_dir

    def get_configs(config_dir: str) -> List[str]:
        # We allow one or more files to be listed after --config or --secrets. Only the first file
        # in the list may NOT end in a ".json" suffix (as a argument not end in that, or and argument
        # starting with a dash, signifies the and of this list). If a file name contains "secret",
        # or is prepended with a special "secret:" or "secrets:" prefix, or if it is listed afer
        # the --secrets option, then it is assumed to contain secrets, which is really just ensures
        # that the values therein won't displayed by default when listing the contents of the file.
        nonlocal argv
        def verify_config(config_file: str, config_dir: str, secret: bool = False) -> Config:
            if secret is True:
                config_secret = True
            elif config_file.lower().startswith("secret:"):
                config_secret = True
                config_file = config_file[len("secret:"):]
            elif config_file.lower().startswith("secrets:"):
                config_secret = True
                config_file = config_file[len("secrets:"):]
            elif "secret" in config_file.lower():
                config_secret = True
            else:
                config_secret = False
            config_file = os.path.normpath(os.path.join(config_dir, config_file)
                                           if not os.path.isabs(config_file) else config_file)
            if not os.path.isfile(config_file):
                _error(f"Configuration file does not exist: {config_file}")
            try:
                with io.open(config_file) as f:
                    config_json = json.load(f)
                    config = Config(config_json, name=config_file, secret=config_secret)
            except Exception as e:
                _error(f"Configuration JSON file cannot be loaded: {config_file}")
            return config
        configs = []
        argi = 0
        while argi < len(argv):
            arg = argv[argi] ; argi += 1  # noqa
            if (arg in ["--config", "-config", "--conf", "-conf"] or
                arg in ["--secrets", "-secrets", "--secret", "-secret"]):
                config_secret = arg in ["--secrets", "-secrets", "--secret", "-secret"]
                argi_config = argi - 1
                if not ((argi < len(argv)) and (config_file := argv[argi])):
                    _usage()
                configs.append(verify_config(config_file, config_dir, secret=config_secret))
                argi += 1
                while argi < len(argv):
                    arg = argv[argi]
                    if arg.startswith("-") or not (config_file := arg).endswith(".json"):
                        del argv[argi_config:argi]
                        argi = 0
                        break
                    argi += 1
                    configs.append(verify_config(config_file, config_dir, secret=config_secret))
                if argi > 0:
                    del argv[argi_config:argi + 1]
        if not configs:
            configs.append(verify_config(DEFAULT_CONFIG_FILE_NAME, config_dir, secret=False))
            configs.append(verify_config(DEFAULT_SECRETS_FILE_NAME, config_dir, secret=True))
        return configs

    config_dir = get_config_dir()
    configs = get_configs(config_dir)

    print(f"config_dir: [{config_dir}]")
    print(f"configs: {configs}")
    for config in configs:
        print(f"configs.name: {config.name}")
        print(f"configs.secret: {config.secret}")
    print(argv)


def _warning(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr, flush=True)


def _error(message: str, usage: bool = False, status: int = 1,
          exception: Optional[Exception] = None, trace: bool = False) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    if usage:
        _usage()
    if isinstance(exception, Exception):
        print(str(exception))
    if trace:
        traceback.print_exc()
    sys.exit(status)


def _usage():
    print(f"{chars.rarrow} hms-config reads named value from {DEFAULT_CONFIG_FILE_NAME} or"
          f" {DEFAULT_SECRETS_FILE_NAME} in: {DEFAULT_CONFIG_DIR}")
    print(f"  {chars.rarrow_hollow} usage: python hms_config.py"
          f" [ path/name [-json] | [-nocolor | -nomerge | -nosort | -json | -yaml | -show] ]")
    sys.exit(1)


if __name__ == "__main__":
    main()
