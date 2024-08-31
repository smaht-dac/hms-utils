from __future__ import annotations
from copy import deepcopy
import io
import json
import os
import re
import sys
import traceback
from typing import Any, List, Optional, Tuple, Union
import yaml
from hms_utils.chars import chars
from hms_utils.print_tree import print_dictionary_tree as print_tree, delete_paths_from_dictionary
from hms_utils.terminal_utils import terminal_color as color

DEFAULT_CONFIG_DIR = os.environ.get("HMS_CONFIG_DIR", "~/.config/hms")
DEFAULT_CONFIG_FILE_NAME = os.environ.get("HMS_CONFIG", "config.json")
DEFAULT_SECRETS_FILE_NAME = os.environ.get("HMS_SECRETS", "secrets.json")
DEFAULT_PATH_SEPARATOR = os.environ.get("HMS_PATH_SEPARATOR", "/")
OBFUSCATED_VALUE = "********"


def main():

    args = parse_args(sys.argv[1:])
    config_file, secrets_file = resolve_files(args)
    config = None
    secrets = None

    try:
        config = Config(config_file,
                        path_separator=args.path_separator,
                        ignore_missing_macro=args.ignore_missing_macro,
                        remove_missing_macro=args.remove_missing_macro,
                        allow_dictionary_target=args.allow_dictionary_target)
    except Exception as e:
        if args.debug or args.config_file_explicit:
            print(f"Cannot open config file: {config_file}")
            if args.debug: traceback.print_exc() ; print(str(e))  # noqa
        sys.exit(1)
    try:
        secrets = Config(secrets_file,
                         path_separator=args.path_separator,
                         ignore_missing_macro=args.ignore_missing_macro,
                         remove_missing_macro=args.remove_missing_macro,
                         allow_dictionary_target=args.allow_dictionary_target)
    except Exception as e:
        if args.debug or args.secrets_file_explicit:
            print(f"Cannot open secret config file: {secrets_file}")
            if args.debug: traceback.print_exc() ; print(str(e))  # noqa
            sys.exit(1)

    if not args.name:
        merged_secrets = None
        unmerged_secrets = None
        if (not args.nomerge) and config and secrets:
            def tree_key_modifier(key_path: str, key: str) -> Optional[str]: # noqa
                nonlocal secrets
                return key if (secrets.lookup(key_path) is None) else color(key, "red", nocolor=args.nocolor)
            def tree_value_modifier(key_path: str, value: str) -> Optional[str]: # noqa
                nonlocal args, secrets, args
                if (not args.show_secrets) and secrets.contains(key_path):
                    value = OBFUSCATED_VALUE
                return value if (secrets.lookup(key_path) is None) else color(value, "red", nocolor=args.nocolor)
            def tree_value_annotator(key_path: str) -> Optional[str]:  # noqa
                nonlocal merged_secrets
                if key_path in unmerged_secrets:
                    return f"{chars.rarrow} unmerged {chars.xmark}"
                return None
            def tree_value_annotator_secrets(key_path: str) -> Optional[str]:  # noqa
                nonlocal merged_secrets
                if key_path in unmerged_secrets:
                    return f"{chars.rarrow} unmerged {chars.xmark}"
                elif key_path in merged_secrets:
                    return f"{chars.rarrow_hollow} merged {chars.check}"
                return None
            def tree_arrow_indicator(key_path: str) -> str:  # noqa
                nonlocal secrets
                return chars.rarrow_hollow if secrets.lookup(key_path) is not None else ""
            if config and secrets:
                merged, merged_secrets, unmerged_secrets = merge_config_and_secrets(
                    config.json, secrets.json,
                    obfuscated_value=None if args.show_secrets else OBFUSCATED_VALUE,
                    path_separator=args.path_separator)
                if not args.nosort:
                    merged = sort_dictionary(merged)
                print(f"\n{config_file}: [secrets{' partially' if unmerged_secrets else ''} merged]")
                print_tree(merged, indent=1, paths=args.show_paths, path_separator=args.path_separator,
                           key_modifier=tree_key_modifier,
                           value_modifier=tree_value_modifier,
                           value_annotator=tree_value_annotator,
                           arrow_indicator=tree_arrow_indicator)
                if unmerged_secrets:
                    print(f"\n{secrets_file}: [secrets unmerged]")
                    #secrets_json = deepcopy(secrets.json)
                    secrets_json = delete_paths_from_dictionary(secrets.json, merged_secrets)
                    print_tree(secrets_json, indent=1, paths=args.show_paths, path_separator=args.path_separator,
                               key_modifier=tree_key_modifier,
                               value_modifier=tree_value_modifier,
                               value_annotator=tree_value_annotator_secrets,
                               arrow_indicator=tree_arrow_indicator)
                    if args.debug:
                        print("\nMerged from secrets:")
                        [print(f"{chars.rarrow} {item}") for item in merged_secrets]
                        print("\nUnmerged from secrets")
                        [print(f"{chars.rarrow} {item}") for item in unmerged_secrets]
                print()
        else:
            if config:
                print(f"\n{config_file}:")
                data = config.json if not args.debug else config.json_raw
                if not args.nosort:
                    data = sort_dictionary(data)
                if args.yaml:
                    print(yaml.dump(data))
                elif args.json:
                    print(json.dumps(data, indent=4))
                else:
                    print_tree(data, indent=1, paths=args.show_paths, path_separator=args.path_separator)
            if secrets:
                print(f"\n{secrets_file}:")
                data = secrets.json if not args.debug else secrets.json_raw
                if args.yaml:
                    print(yaml.dump(data))
                elif args.json:
                    print(json.dumps(data, indent=4))
                else:
                    print_tree(data, indent=1, paths=args.show_paths, path_separator=args.path_separator,
                               value_modifier=lambda key_path, value: OBFUSCATED_VALUE)
            if unmerged_secrets:
                print(f"\nSecret not mergeable into config:")
                for unmerged_secret_key in unmerged_secrets:
                    print(f"▷ {unmerged_secret_key}")
        exit(0)

    if ((value := config.lookup(args.name)) is not None) or ((value := secrets.lookup(args.name)) is not None):
        print(value)
        sys.exit(0)
    sys.exit(1)


def parse_args(argv: List[str]) -> object:

    class Args:
        config_dir = os.path.expanduser(DEFAULT_CONFIG_DIR)
        config_file = DEFAULT_CONFIG_FILE_NAME
        secrets_file = DEFAULT_SECRETS_FILE_NAME
        config_file_explicit = False
        secrets_file_explicit = False
        config_dir_explicit = False
        path_separator = DEFAULT_PATH_SEPARATOR
        ignore_missing_macro = True
        remove_missing_macro = False
        allow_dictionary_target = False
        show_secrets = False
        show_paths = False
        name = None
        yaml = False
        json = False
        nosort = False
        nomerge = False
        nocolor = False
        verbose = False
        dump = False
        debug = False

    args = Args() ; argi = 0 ; argn = len(argv)  # noqa
    while argi < argn:
        arg = argv[argi] ; argi += 1  # noqa
        if (arg == "--dir") or (arg == "-dir") or (arg == "--directory") or (arg == "-directory"):
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                usage()
            args.config_dir = arg
            args.config_dir_explicit = True
            argi += 1
        elif (arg == "--config") or (arg == "-config") or (arg == "--conf") or (arg == "-conf"):
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                usage()
            args.config_file = arg
            args.config_file_explicit = True
            argi += 1
        elif ((arg == "--secrets-config") or (arg == "-secrets-config") or
              (arg == "--secrets-conf") or (arg == "-secrets-conf") or
              (arg == "--secret-config") or (arg == "-secret-config") or
              (arg == "--secret-conf") or (arg == "-secret-conf") or
              (arg == "--secrets") or (arg == "-secrets") or
              (arg == "--secret") or (arg == "-secret")):
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                usage()
            args.secrets_file = arg
            args.secrets_file_explicit = True
            argi += 1
        elif ((arg == "--path-separator") or (arg == "-path-separator") or
              (arg == "--separator") or (arg == "-separator") or
              (arg == "--sep") or (arg == "-sep")):
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                usage()
            args.path_separator = arg
            argi += 1
        elif (arg == "--allow-dictionary-target") or (arg == "-allow-dictionary-target"):
            args.allow_dictionary_target = True
        elif (arg == "--ignore-missing-macro") or (arg == "-ignore-missing-macro"):
            args.ignore_missing_macro = True
        elif (arg == "--remove-missing-macro") or (arg == "-remove-missing-macro"):
            args.remove_missing_macro = True
        elif ((arg == "--show-secrets") or (arg == "-show-secrets") or
              (arg == "--show-secret") or (arg == "-show-secret") or
              (arg == "--show") or (arg == "-show")):
            args.show_secrets = True
        elif ((arg == "--show-paths") or (arg == "-show-paths") or
              (arg == "--show-path") or (arg == "-show-path") or
              (arg == "--paths") or (arg == "-paths") or
              (arg == "--path") or (arg == "-path")):
            args.show_paths = True
        elif (arg == "--yaml") or (arg == "-yaml") or (arg == "--yml") or (arg == "-yml"):
            args.yaml = True
        elif (arg == "--json") or (arg == "-json"):
            args.json = True
        elif (arg == "--nosort") or (arg == "-nosort"):
            args.nosort = True
        elif (arg == "--nomerge") or (arg == "-nomerge"):
            args.nomerge = True
        elif (arg == "--nocolor") or (arg == "-nocolor"):
            args.nocolor = True
        elif (arg == "--dump") or (arg == "-dump"):
            args.dump = True
        elif (arg == "--verbose") or (arg == "-verbose"):
            args.verbose = True
        elif (arg == "--debug") or (arg == "-debug"):
            args.debug = True
        elif (arg == "--help") or (arg == "-help") or (arg == "help"):
            usage()
        elif arg.startswith("-"):
            usage()
        elif args.name:
            usage()
        else:
            args.name = arg
    return args


def resolve_files(args: List[str]) -> Tuple[Optional[str], Optional[str]]:

    def resolve_file_path(file: str, directory: Optional[str] = None,
                          file_explicit: bool = False, directory_explicit: bool = False) -> Optional[str]:
        if os.path.isabs(file := os.path.normpath(file or "")):
            if not os.path.exists(file):
                return None
            return file
        elif file_explicit and os.path.exists(file) and (not os.path.isdir(file)) and (not directory_explicit):
            if not os.path.isabs(file):
                file = os.path.join(os.path.abspath(os.curdir), file)
            return file
        elif os.path.isabs(directory := os.path.normpath(directory or "")):
            if not os.path.isdir(directory):
                return None
        if not os.path.isdir(directory := os.path.normpath(os.path.join(os.path.abspath(os.curdir), directory))):
            return None
        elif not os.path.exists(file := os.path.join(directory, file)):
            return None
        return file

    config_dir = args.config_dir
    config_file = args.config_file
    secrets_file = args.secrets_file

    if not (config_file := resolve_file_path(config_file, config_dir,
                                             file_explicit=args.config_file_explicit,
                                             directory_explicit=args.config_dir_explicit)):
        if args.config_file_explicit:
            print(f"Cannot find config file: {config_file}")
            sys.exit(1)
    if not (secrets_file := resolve_file_path(secrets_file, config_dir,
                                              file_explicit=args.config_file_explicit,
                                              directory_explicit=args.config_dir_explicit)):
        if args.secrets_file_explicit:
            print(f"Cannot find secret config file: {args.config_file_explicit}")
            sys.exit(1)

    return config_file, secrets_file


def merge_config_and_secrets(config: dict, secrets: dict,
                             obfuscated_value: str = OBFUSCATED_VALUE,
                             path_separator: str = "/") -> Tuple[dict, list, list]:
    if not (isinstance(config, dict) or isinstance(secrets, dict)):
        return None, None
    merged = deepcopy(config) ; merged_secrets = [] ; unmerged_secrets = []  # noqa
    secrets = obfuscate_secrets(secrets) if obfuscated_value else secrets
    def merge(config: dict, secrets: dict, path: str = "") -> None:  # noqa
        nonlocal unmerged_secrets, path_separator
        for key, value in secrets.items():
            key_path = f"{path}{path_separator}{key}" if path else key
            if key not in config:
                config[key] = secrets[key]
                merged_secrets.append(key_path)
            elif isinstance(config[key], dict) and isinstance(secrets[key], dict):
                merge(config[key], secrets[key], path=key_path)
            else:
                unmerged_secrets.append(key_path)
    merge(merged, secrets)
    return merged, merged_secrets, unmerged_secrets


def obfuscate_secrets(secrets: dict, obfuscated_value: str = OBFUSCATED_VALUE) -> dict:
    obfuscated_secrets = {}
    for key, value in secrets.items():
        obfuscated_secrets[key] = obfuscate_secrets(value) if isinstance(value, dict) else obfuscated_value
    return obfuscated_secrets


def sort_dictionary(data: dict) -> dict:
    if not isinstance(data, dict):
        return data
    sorted_data = {}
    for key in sorted(data.keys()):
        sorted_data[key] = sort_dictionary(data[key])
    return sorted_data


class Config:

    _PARENT = "@@@__PARENT__@@@"
    _MACRO_PATTERN = re.compile(r"\$\{([^}]+)\}")

    def __init__(self, file_or_dictionary: Union[str, dict],
                 path_separator: bool = ".",
                 ignore_missing_macro: bool = False,
                 remove_missing_macro: bool = False,
                 allow_dictionary_target: bool = False,
                 expand_macros: bool = True) -> None:
        self._config = None
        self._path_separator = path_separator
        self._expand_macros = expand_macros
        self._ignore_missing_macro = ignore_missing_macro
        self._remove_missing_macro = remove_missing_macro
        self._allow_dictionary_target = allow_dictionary_target
        self._imap = {}
        self._load_config(file_or_dictionary)

    def contains(self, name: str) -> bool:
        return self.lookup(name) is not None

    def lookup(self, name: str, config: Optional[dict] = None) -> Optional[str]:
        if config is None:
            config = self._config
        value = None
        for name_component in name.split(self._path_separator):
            if value is not None:
                return None
            if not (name_component := name_component.strip()):
                continue
            if not (value := config.get(name_component)):
                return None
            if isinstance(value, dict):
                config = value
                value = None
        if value is not None:
            return value
        elif config and self._allow_dictionary_target:
            return str(self._cleanup_json(config))
        return None

    @property
    def json(self) -> dict:
        return self._cleanup_json(self._config)

    @property
    def json_raw(self) -> dict:
        return self._config

    def _load_config(self, file_or_dictionary: Union[str, dict]) -> None:
        if isinstance(file_or_dictionary, dict):
            self._config = file_or_dictionary
        else:
            with io.open(file_or_dictionary, "r") as f:
                self._config = json.load(f)
        if self._expand_macros:
            _ = self._macro_expand_json(self._config)

    def _macro_expand_json(self, data: dict) -> dict:

        def set_parent(item: dict, parent: dict) -> None:
            nonlocal self
            parent_id = id(parent)
            self._imap[parent_id] = parent
            item[Config._PARENT] = parent_id

        def get_parent(item: dict) -> Optional[dict]:
            nonlocal self
            return self._imap.get(item.get(Config._PARENT))

        def is_parent(name: str) -> None:
            return name == Config._PARENT

        def is_primitive_type(value: Any) -> bool:
            return isinstance(value, (int, float, str, bool))

        def lookup_macro_value(macro_name: str, data: dict) -> Optional[Union[int, float, str, bool]]:
            nonlocal self
            if (macro_value := self.lookup(macro_name, data)) is not None:
                if is_primitive_type(macro_value):
                    return macro_value
                return None
            data = get_parent(data)
            while data:
                if (macro_value := self.lookup(macro_name, data)) is not None:
                    if is_primitive_type(macro_value):
                        return macro_value
                    return None
                data = get_parent(data)
            return None

        def macro_expand_value(value, data):  # noqa
            nonlocal self
            expanding_macros = set()
            missing_macro_found = False
            while True:
                if not (match := Config._MACRO_PATTERN.search(value)):
                    break
                if (macro_name := match.group(1)) and (macro_value := lookup_macro_value(macro_name, data)):
                    if macro_name in expanding_macros:
                        raise Exception(f"Circular macro definition found: {macro_name}")
                    expanding_macros.add(macro_name)
                    value = value.replace(f"${{{macro_name}}}", macro_value)
                elif self._ignore_missing_macro:
                    missing_macro_found = True
                    value = value.replace(f"${{{macro_name}}}", f"@@@__[{macro_name}]__@@@")
                elif self._remove_missing_macro:
                    value = value.replace(f"${{{macro_name}}}", "")
                else:
                    raise Exception(f"Macro name not found: {macro_name}")
            if missing_macro_found and self._ignore_missing_macro:
                value = value.replace("@@@__[", "${")
                value = value.replace("]__@@@", "}")
            return value

        for name in data:  # TODO: check for duplicate keys.
            if not ((name := name.strip()) and (not is_parent(name))):
                continue
            if isinstance(data[name], dict):
                set_parent(data[name], data)
                data[name] = self._macro_expand_json(data[name])
            elif not is_primitive_type(data[name]):
                raise Exception(f"Non-primitive type found: {name}")
            else:
                data[name] = macro_expand_value(str(data[name]), data)

        return data

    @staticmethod
    def _cleanup_json(data: dict) -> dict:
        if isinstance(data, dict):
            if Config._PARENT in data:
                del data[Config._PARENT]
            for key, value in list(data.items()):
                Config._cleanup_json(value)
        return data


def usage():
    print(f"Reads named value from {DEFAULT_CONFIG_FILE_NAME} or"
          f" {DEFAULT_SECRETS_FILE_NAME} in: {DEFAULT_CONFIG_DIR}")
    print("usage: python hms_config.py name")
    sys.exit(1)


if __name__ == "__main__":
    main()
