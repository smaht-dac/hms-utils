from __future__ import annotations
from copy import deepcopy
import io
import json
import os
import re
from pkg_resources import get_distribution as get_package_version
import stat
import sys
import traceback
from typing import Any, List, Optional, Tuple, Union
import yaml
from hms_utils.chars import chars
from hms_utils.dictionary_utils import (
    delete_paths_from_dictionary, print_dictionary_list,
    print_dictionary_tree, sort_dictionary
)
from hms_utils.terminal_utils import terminal_color as color

DEFAULT_CONFIG_DIR = os.environ.get("HMS_CONFIG_DIR", "~/.config/hms")
DEFAULT_CONFIG_FILE_NAME = os.environ.get("HMS_CONFIG", "config.json")
DEFAULT_SECRETS_FILE_NAME = os.environ.get("HMS_SECRETS", "secrets.json")
DEFAULT_PATH_SEPARATOR = os.environ.get("HMS_PATH_SEPARATOR", "/")
DEFAULT_EXPORT_NAME_SEPARATOR = os.environ.get("HMS_EXPORT_NAME_SEPARATOR", ":")
OBFUSCATED_VALUE = "********"


def main():

    args = parse_args(sys.argv[1:])

    try:
        config = Config(args.config_file, path_separator=args.path_separator)
    except Exception as e:
        print(f"Cannot process config file: {args.config_file}")
        if args.debug: traceback.print_exc() ; print(str(e))  # noqa
        sys.exit(1)

    secrets = None
    if args.secrets_file:
        try:
            secrets = Config(args.secrets_file, path_separator=args.path_separator)
        except Exception as e:
            print(f"Cannot process secrets file: {args.secrets_file}")
            if args.debug: traceback.print_exc() ; print(str(e))  # noqa
            sys.exit(1)

    if not args.names:
        print_config_and_secrets(config, secrets, args)
        exit(0)

    status = 0
    if args.export:
        if args.export_file and os.path.exists(args.export_file):
            print(f"Export file must not already exist: {args.export_file}")
            exit(1)
        exports = []
        for name in args.names:
            if (colon := name.find(DEFAULT_EXPORT_NAME_SEPARATOR)) > 0:
                export_name = name[0:colon]
                if not (name := name[colon + 1:].strip()):
                    continue
            else:
                export_name = path_basename(name, args.path_separator)
            if (((value := config.lookup(name, allow_dictionary=args.json)) is not None) or
                ((value := secrets.lookup(name, allow_dictionary=args.json)) is not None)):  # noqa
                exports.append(f"export {export_name}={value}")
            else:
                status = 1
        if args.export_file:
            if args.verbose:
                print(f"Writing exports to file: {args.export_file}")
            with io.open(args.export_file, "w") as f:
                for export in exports:
                    if args.verbose:
                        print(f"{chars.rarrow_hollow} {export}")
                    f.write(f"{export}\n")
        else:
            for export in exports:
                print(export)
    else:
        for name in args.names:
            if (((value := config.lookup(name, allow_dictionary=args.json)) is not None) or
                ((value := secrets.lookup(name, allow_dictionary=args.json)) is not None)):  # noqa
                print(value)
            else:
                status = 1

    sys.exit(status)


def parse_args(argv: List[str]) -> object:

    class Args:
        config_dir = os.path.expanduser(DEFAULT_CONFIG_DIR)
        config_file = DEFAULT_CONFIG_FILE_NAME
        secrets_file = DEFAULT_SECRETS_FILE_NAME
        config_file_explicit = False
        secrets_file_explicit = False
        config_dir_explicit = False
        path_separator = DEFAULT_PATH_SEPARATOR
        name = None
        names = []
        list = False
        yaml = False
        json = False
        show_secrets = False
        show_paths = False
        nocolor = False
        nomerge = False
        nosort = False
        export = False
        export_file = None
        verbose = False
        debug = False

    args = Args() ; argi = 0 ; argn = len(argv)  # noqa
    while argi < argn:
        arg = argv[argi] ; argi += 1  # noqa
        if arg in ["--function", "-function", "--shell", "-shell"]:
            print(os.path.join(os.path.dirname(os.path.abspath(__file__)), "hms_config.sh"))
            exit(1)
        elif arg in ["--dir", "-dir", "--directory", "-directory"]:
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                usage()
            args.config_dir = arg ; args.config_dir_explicit = True ; argi += 1  # noqa
        elif arg in ["--config", "-config", "--conf", "-conf"]:
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                usage()
            args.config_file = arg ; args.config_file_explicit = True ; argi += 1  # noqa
        elif arg in ["--secrets-config", "-secrets-config", "--secrets-conf", "-secrets-conf", "--secret-config",
                     "-secret-config", "--secret-conf", "-secret-conf", "--secrets", "-secrets", "--secret", "-secret"]:
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                usage()
            args.secrets_file = arg ; args.secrets_file_explicit = True ; argi += 1  # noqa
        elif arg in ["--path-separator", "-path-separator", "--separator", "-separator", "--sep", "-sep"]:
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                usage()
            args.path_separator = arg ; argi += 1  # noqa
        elif arg in ["--show-secrets", "-show-secrets", "--show-secret", "-show-secret", "--show", "-show"]:
            args.show_secrets = True
        elif arg in ["--show-paths", "-show-paths", "--show-path",
                     "-show-path", "--paths", "-paths", "--path", "-path"]:
            args.show_paths = True
        elif arg in ["--list", "-list"]:
            args.list = True
        elif arg in ["--yaml", "-yaml", "--yml", "-yml"]:
            args.yaml = True
        elif arg in ["--json", "-json"]:
            args.json = True
        elif arg in ["--nocolor", "-nocolor"]:
            args.nocolor = True
        elif arg in ["--nomerge", "-nomerge"]:
            args.nomerge = True
        elif arg in ["--nosort", "-nosort"]:
            args.nosort = True
        elif arg in ["--export", "-export"]:
            args.export = True
        elif arg in ["--export-file", "-export-file"]:
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                usage()
            args.export = True
            args.export_file = argv[argi] ; argi += 1  # noqa
        elif arg in ["--debug", "-debug"]:
            args.debug = True
        elif arg in ["--verbose", "-verbose"]:
            args.verbose = True
        elif arg in ["--version", "-version"]:
            print(f"hms-utils version: {get_version()}")
            usage()
        elif (arg in ["--help", "-help"]) or arg.startswith("-"):
            usage()
        else:
            args.names.append(arg)

    if args.names and (args.show_secrets or args.show_paths or args.yaml or
                       args.nosort or args.nomerge or args.nocolor or args.yaml or args.list):
        print("Option not allowed with a config name/path argument.")
        usage()
    elif args.export and (not args.names):
        print("The --export option must be used with a config name/path argument.")
        usage()

    config_file, secrets_file = resolve_files(args)
    if not config_file:
        print("No config file found.")
        usage()
    args.config_file = config_file
    args.secrets_file = secrets_file
    return args


def print_config_and_secrets(config: Config, secrets: Config, args: object) -> None:
    if (not args.nomerge) and (not args.json) and (not args.yaml) and config and secrets:
        print_config_and_secrets_merged(config, secrets, args)
    else:
        print_config_and_secrets_unmerged(config, secrets, args)
        return


def print_config_and_secrets_merged(config: Config, secrets: Config, args: object) -> None:

    merged_secrets = None
    unmerged_secrets = None

    def tree_key_modifier(key_path: str, key: Optional[str] = None) -> Optional[str]:
        nonlocal args, secrets
        return ((key or key_path) if (secrets.lookup(key_path) is None)
                else color(key or key_path, "red", nocolor=args.nocolor))

    def tree_value_modifier(key_path: str, value: str) -> Optional[str]:
        nonlocal args, secrets
        if (not args.show_secrets) and secrets.contains(key_path):
            value = OBFUSCATED_VALUE
        return value if (secrets.lookup(key_path) is None) else color(value, "red", nocolor=args.nocolor)

    def tree_value_annotator(key_path: str) -> Optional[str]:
        nonlocal merged_secrets
        if key_path in unmerged_secrets:
            return f"{chars.rarrow} unmerged {chars.xmark}"
        return None

    def tree_value_annotator_secrets(key_path: str) -> Optional[str]:
        nonlocal merged_secrets, unmerged_secrets
        if key_path in unmerged_secrets:
            return f"{chars.rarrow} unmerged {chars.xmark}"
        elif key_path in merged_secrets:
            return f"{chars.rarrow_hollow} merged {chars.check}"
        return None

    def tree_arrow_indicator(key_path: str) -> str:
        nonlocal secrets
        return chars.rarrow_hollow if secrets.lookup(key_path) is not None else ""

    if config and secrets:
        merged, merged_secrets, unmerged_secrets = merge_config_and_secrets(config.json, secrets.json,
                                                                            path_separator=args.path_separator)
        if not args.nosort:
            merged = sort_dictionary(merged)
        print(f"\n{config.file}: [secrets{' partially' if unmerged_secrets else ''} merged]")
        if args.list:
            print_dictionary_list(merged, path_separator=args.path_separator,
                                  prefix=f" {chars.rarrow_hollow} ",
                                  key_modifier=tree_key_modifier,
                                  value_modifier=tree_value_modifier,
                                  value_annotator=tree_value_annotator)
        else:
            print_dictionary_tree(merged, indent=1, paths=args.show_paths, path_separator=args.path_separator,
                                  key_modifier=tree_key_modifier,
                                  value_modifier=tree_value_modifier,
                                  value_annotator=tree_value_annotator,
                                  arrow_indicator=tree_arrow_indicator)
        if unmerged_secrets:
            print(f"\n{secrets.file}: [secrets unmerged]")
            secrets_json = delete_paths_from_dictionary(secrets.json, merged_secrets)
            if args.list:
                print_dictionary_list(secrets_json, path_separator=args.path_separator,
                                      prefix=f" {chars.rarrow_hollow} ",
                                      key_modifier=tree_key_modifier,
                                      value_modifier=tree_value_modifier,
                                      value_annotator=tree_value_annotator)
            else:
                print_dictionary_tree(secrets_json, indent=1, paths=args.show_paths, path_separator=args.path_separator,
                                      key_modifier=tree_key_modifier,
                                      value_modifier=tree_value_modifier,
                                      value_annotator=tree_value_annotator_secrets,
                                      arrow_indicator=tree_arrow_indicator)
            if args.debug:
                print("\nMerged from secrets:") ; [print(f"- {item}") for item in merged_secrets]  # noqa
                print("\nUnmerged from secrets") ; [print(f"- {item}") for item in unmerged_secrets]  # noqa
        print()


def print_config_and_secrets_unmerged(config: Config, secrets: Config, args: object) -> None:
    if config:
        print(f"\n{config.file}:")
        data = config.json if not args.debug else config.rawjson
        if not args.nosort:
            data = sort_dictionary(data)
        if args.yaml:
            print(yaml.dump(data))
        elif args.json:
            print(json.dumps(data, indent=4))
        elif args.list:
            print_dictionary_list(data, path_separator=args.path_separator, prefix=f" {chars.rarrow_hollow} ")
        else:
            print_dictionary_tree(data, indent=1, paths=args.show_paths, path_separator=args.path_separator)
    if secrets:
        print(f"\n{secrets.file}:")
        data = secrets.json if not args.debug else secrets.rawjson
        if args.yaml:
            print(yaml.dump(data))
        elif args.json:
            print(json.dumps(data, indent=4))
        else:
            if args.list:
                print_dictionary_list(data, path_separator=args.path_separator, prefix=f" {chars.rarrow_hollow} ")
            else:
                print_dictionary_tree(
                    data, indent=1,
                    paths=args.show_paths, path_separator=args.path_separator,
                    value_modifier=None if args.show_secrets else lambda key_path, value: OBFUSCATED_VALUE)
    print()


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

    def ensure_secrets_file_protected(file: str) -> bool:
        try:
            return stat.S_IMODE(os.stat(file).st_mode) in (0o600, 0o400)
        except Exception:
            return False

    config_file = args.config_file
    secrets_file = args.secrets_file

    if not (config_file := resolve_file_path(config_file, args.config_dir,
                                             file_explicit=args.config_file_explicit,
                                             directory_explicit=args.config_dir_explicit)):
        if args.config_file_explicit:
            print(f"Cannot find config file: {config_file}")
            sys.exit(1)
    if not (secrets_file := resolve_file_path(secrets_file, args.config_dir,
                                              file_explicit=args.config_file_explicit,
                                              directory_explicit=args.config_dir_explicit)):
        if args.secrets_file_explicit:
            print(f"Cannot find secrets file: {args.config_file_explicit}")
            sys.exit(1)
    elif not ensure_secrets_file_protected(secrets_file):
        print(f"{color('WARNING', 'red')}: Your secrets file is not read protected for others: {secrets_file}")

    return config_file, secrets_file


def merge_config_and_secrets(config: dict, secrets: dict, path_separator: str = "/") -> Tuple[dict, list, list]:
    if not (isinstance(config, dict) or isinstance(secrets, dict)):
        return None, None
    merged = deepcopy(config) ; merged_secrets = [] ; unmerged_secrets = []  # noqa
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


def path_basename(name: str, separator: str = "/") -> str:
    if (index := name.rfind(separator)) > 0:
        return name[index + 1:]
    return name


class Config:

    _PARENT = "@@@__PARENT__@@@"
    _MACRO_PATTERN = re.compile(r"\$\{([^}]+)\}")

    def __init__(self, file_or_dictionary: Union[str, dict], path_separator: bool = ".") -> None:
        self._json = None
        self._path_separator = path_separator
        # These booleans are effectively immutable; decided on this default/unchangable behavior.
        self._expand_macros = True
        self._ignore_missing_macro = True
        self._remove_missing_macro = True
        self._stringize_non_primitive_types = True
        self._imap = {}
        self._load(file_or_dictionary)

    def contains(self, name: str) -> bool:
        return self.lookup(name) is not None

    def lookup(self, name: str, config: Optional[dict] = None, allow_dictionary: bool = False) -> Optional[str]:
        if config is None:
            config = self._json
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
        elif config and allow_dictionary:
            return str(self._cleanjson(config))
        return None

    @property
    def file(self) -> dict:
        return self._file

    @property
    def json(self) -> dict:
        return self._cleanjson(self._json)

    @property
    def rawjson(self) -> dict:
        return self._json

    def _load(self, file_or_dictionary: Union[str, dict]) -> None:
        if isinstance(file_or_dictionary, dict):
            self._json = file_or_dictionary
        else:
            self._file = file_or_dictionary
            with io.open(file_or_dictionary, "r") as f:
                self._json = json.load(f)
        if self._expand_macros:
            _ = self._macro_expand_json(self._json)

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

        def lookup_macro_value(macro_name: str, data: dict) -> Optional[str]:
            nonlocal self
            if (macro_value := self.lookup(macro_name, data)) is not None:
                if is_primitive_type(macro_value):
                    return str(macro_value)
                return None
            data = get_parent(data)
            while data:
                if (macro_value := self.lookup(macro_name, data)) is not None:
                    if is_primitive_type(macro_value):
                        return str(macro_value)
                    return None
                data = get_parent(data)
            return None

        def macro_expand_value(value: str, data: dict) -> Optional[str]:
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
            elif not is_primitive_type(data[name]) and not self._stringize_non_primitive_types:
                raise Exception(f"Non-primitive type found: {name}")
            else:
                data[name] = macro_expand_value(str(data[name]), data)

        return data

    @staticmethod
    def _cleanjson(data: dict) -> dict:
        if isinstance(data, dict):
            if Config._PARENT in data:
                del data[Config._PARENT]
            for key, value in list(data.items()):
                Config._cleanjson(value)
        return data


def get_version(package_name: str = "hms-utils") -> str:
    try:
        return get_package_version(package_name).version
    except Exception:
        return ""


def usage():
    print(f"{chars.rarrow} hms-config reads named value from {DEFAULT_CONFIG_FILE_NAME} or"
          f" {DEFAULT_SECRETS_FILE_NAME} in: {DEFAULT_CONFIG_DIR}")
    print(f"  {chars.rarrow_hollow} usage: python hms_config.py"
          f" [ path/name [-json] | [-nocolor | -nomerge | -nosort | -json | -yaml | -show] ]")
    sys.exit(1)


if __name__ == "__main__":
    main()
