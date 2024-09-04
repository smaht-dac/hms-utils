from __future__ import annotations
from copy import deepcopy
import io
import json
import os
import re
from importlib.metadata import version as get_package_version
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

DEFAULT_CONFIG_DIR = "~/.config/hms"
DEFAULT_CONFIG_FILE_NAME = "config.json"
DEFAULT_SECRETS_FILE_NAME = "secrets.json"
DEFAULT_PATH_SEPARATOR = "/"
DEFAULT_EXPORT_NAME_SEPARATOR = ":"
OBFUSCATED_VALUE = "********"


def main():

    args = parse_args(sys.argv[1:])

    config = None
    if args.config_file:
        try:
            config = Config(args.config_file, path_separator=args.path_separator, nomacros=args.nomacros)
        except Exception as e:
            error(f"Cannot process config file: {args.config_file}", exception=e, trace=True)

    secrets = None
    if args.secrets_file:
        try:
            secrets = Config(args.secrets_file, path_separator=args.path_separator, nomacros=args.nomacros)
        except Exception as e:
            error(f"Cannot process secrets file: {args.secrets_file}", exception=e, trace=True)

    if not args.names:
        print_config_and_secrets(config, secrets, args)
        exit(0)

    status = 0
    if args.export:
        if args.export_file and os.path.exists(args.export_file):
            error(f"Export file must not already exist: {args.export_file}")
        exports = []
        for name in args.names:
            if (colon := name.find(DEFAULT_EXPORT_NAME_SEPARATOR)) > 0:
                export_name = name[0:colon]
                if not (name := name[colon + 1:].strip()):
                    continue
            else:
                export_name = path_basename(name, args.path_separator)
            found = False ; found_dictionary = False  # noqa
            if ((config and ((value := config.lookup(name, allow_dictionary=True)) is not None)) or
                (secrets and ((value := secrets.lookup(name, allow_dictionary=True)) is not None))):  # noqa
                if isinstance(value, dict):
                    # Special case: If target name/path is a dictionary then
                    # generate exports for every (non-dictionary) key/value within.
                    found_dictionary = True
                    for key in value:
                        if not isinstance(value[key], dict):
                            exports.append(f"export {key}={value[key]}")
                            found = True
                else:
                    exports.append(f"export {export_name}={value}")
                    found = True
            if not found:
                if args.verbose:
                    if found_dictionary:
                        warning(f"{chars.rarrow} Config name/path contains no direct values: {name}")
                    else:
                        warning(f"{chars.rarrow} Config name/path not found: {name}")
                status = 1
        if args.export_file:
            if args.verbose:
                print(f"Writing exports to file: {args.export_file}")
            with io.open(args.export_file, "w") as f:
                for export in sorted(exports):
                    if args.verbose:
                        print(f"{chars.rarrow_hollow} {export}")
                    f.write(f"{export}\n")
        else:
            for export in sorted(exports):
                print(export)
    else:
        for name in args.names:
            if ((config and ((value := config.lookup(name, allow_dictionary=args.json)) is not None)) or
                (secrets and ((value := secrets.lookup(name, allow_dictionary=args.json)) is not None))):  # noqa
                if args.json_formatted and isinstance(value, dict):
                    print(json.dumps(value, indent=4))
                else:
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
        json_formatted = False
        show_secrets = False
        show_paths = False
        nocolor = False
        nomerge = False
        nosort = False
        nomacros = False
        export = False
        export_file = None
        verbose = False
        debug = False

    args = Args()

    if value := os.environ.get("HMS_CONFIG_DIR"):
        args.config_dir = value
        args.config_dir_explicit = True
    if value := os.environ.get("HMS_CONFIG"):
        args.config_file = value
        args.config_file_explicit = True
    if value := os.environ.get("HMS_SECRETS"):
        args.secrets_file = value
        args.secrets_file_explicit = True

    argi = 0 ; argn = len(argv)  # noqa
    while argi < argn:
        arg = argv[argi] ; argi += 1  # noqa
        if arg in ["--functions", "-functions", "--function", "-function", "--shell", "-shell"]:
            print(os.path.join(os.path.dirname(os.path.abspath(__file__)), "hms_config.sh"))
            exit(0)
        elif arg in ["--dir", "-dir", "--directory", "-directory"]:
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                _usage()
            args.config_dir = arg ; args.config_dir_explicit = True ; argi += 1  # noqa
        elif arg in ["--config", "-config", "--conf", "-conf"]:
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                _usage()
            args.config_file = arg ; args.config_file_explicit = True ; argi += 1  # noqa
        elif arg in ["--secrets-config", "-secrets-config", "--secrets-conf", "-secrets-conf", "--secret-config",
                     "-secret-config", "--secret-conf", "-secret-conf", "--secrets", "-secrets", "--secret", "-secret"]:
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                _usage()
            args.secrets_file = arg ; args.secrets_file_explicit = True ; argi += 1  # noqa
        elif arg in ["--path-separator", "-path-separator", "--separator", "-separator", "--sep", "-sep"]:
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                _usage()
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
        elif arg in ["--jsonf", "-jsonf"]:
            args.json = True
            args.json_formatted = True
        elif arg in ["--nocolor", "-nocolor"]:
            args.nocolor = True
        elif arg in ["--nomerge", "-nomerge"]:
            args.nomerge = True
        elif arg in ["--nosort", "-nosort"]:
            args.nosort = True
        elif arg in ["--nomacros", "-nomacros", "--nomacro", "-nomacro"]:
            args.nomacros = True
        elif arg in ["--export", "-export", "--exports", "-exports"]:
            args.export = True
        elif arg in ["--export-file", "-export-file"]:
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                _usage()
            args.export = True
            args.export_file = argv[argi] ; argi += 1  # noqa
        elif arg in ["--debug", "-debug"]:
            args.debug = True
        elif arg in ["--verbose", "-verbose"]:
            args.verbose = True
        elif arg in ["--version", "-version"]:
            print(f"hms-utils version: {get_version()}")
            _usage()
        elif (arg in ["--help", "-help"]) or arg.startswith("-"):
            _usage()
        else:
            args.names.append(arg)

    # If either config or secrets file is explicit ignore the other implicit one.
    if args.config_file_explicit:
        if not args.secrets_file_explicit:
            args.secrets_file = None
    elif args.secrets_file_explicit:
        args.config_file = None

    if args.names and (args.show_secrets or args.show_paths or
                       args.yaml or args.nosort or args.nomerge or
                       args.nomacros or args.nocolor or args.yaml or args.list):
        error("Option not allowed with a config name/path argument.", usage=True)
    elif args.export and (not args.names):
        error("The --export option must be used with a config name/path argument.", usage=True)

    config_file, secrets_file = resolve_files(args)
    if (not config_file) and (not secrets_file):
        error("No config or secrets file found.", usage=True)
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
        return ((key or key_path) if ((not secrets) or (secrets.lookup(key_path) is None))
                else color(key or key_path, "red", nocolor=args.nocolor))

    def tree_value_modifier(key_path: str, value: str) -> Optional[str]:
        nonlocal args, secrets
        if (not args.show_secrets) and secrets and secrets.contains(key_path):
            value = OBFUSCATED_VALUE
        return value if ((not secrets) or
                         (secrets.lookup(key_path) is None)) else color(value, "red", nocolor=args.nocolor)

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
        return chars.rarrow_hollow if (secrets and (secrets.lookup(key_path) is not None)) else ""

    if config and secrets:
        merged, merged_secrets, unmerged_secrets = merge_config_and_secrets(config.json, secrets.json,
                                                                            path_separator=args.path_separator)
        if not args.nosort:
            merged = sort_dictionary(merged)
        print(f"\n{config.file}: [with {os.path.basename(args.secrets_file)}"
              f"{' partially' if unmerged_secrets else ''} merged in]")
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

    def tree_key_modifier(key_path: str, key: Optional[str] = None) -> Optional[str]:
        nonlocal args, secrets
        return ((key or key_path) if ((not secrets) or (secrets.lookup(key_path) is None))
                else color(key or key_path, "red", nocolor=args.nocolor))

    def tree_value_modifier(key_path: str, value: str) -> Optional[str]:
        nonlocal args, secrets
        if (not args.show_secrets) and secrets and secrets.contains(key_path):
            value = OBFUSCATED_VALUE
        return value if ((not secrets) or
                         (secrets.lookup(key_path) is None)) else color(value, "red", nocolor=args.nocolor)

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
            print_dictionary_tree(data, indent=1, paths=args.show_paths, path_separator=args.path_separator,
                                  key_modifier=tree_key_modifier,
                                  value_modifier=tree_value_modifier)
    if secrets:
        print(f"\n{secrets.file}:")
        data = secrets.json if not args.debug else secrets.rawjson
        if args.yaml:
            print(yaml.dump(data))
        elif args.json:
            print(json.dumps(data, indent=4))
        else:
            if args.list:
                print_dictionary_list(data, path_separator=args.path_separator, prefix=f" {chars.rarrow_hollow} ",
                                      key_modifier=tree_key_modifier,
                                      value_modifier=tree_value_modifier)
            else:
                print_dictionary_tree(
                    data, indent=1,
                    paths=args.show_paths, path_separator=args.path_separator,
                    key_modifier=tree_key_modifier,
                    value_modifier=tree_value_modifier)
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

    if config_file:
        if not (config_file := resolve_file_path(config_file, args.config_dir,
                                                 file_explicit=args.config_file_explicit,
                                                 directory_explicit=args.config_dir_explicit)):
            if args.config_file.endswith(".json"):
                config_file = args.config_file[:-5] + ".yaml"
                config_file = resolve_file_path(config_file, args.config_dir,
                                                file_explicit=args.config_file_explicit,
                                                directory_explicit=args.config_dir_explicit)
        if (not config_file) and args.config_file_explicit:
            error(f"Config file not found: {args.config_file}")

    if secrets_file:
        if not (secrets_file := resolve_file_path(secrets_file, args.config_dir,
                                                  file_explicit=args.secrets_file_explicit,
                                                  directory_explicit=args.config_dir_explicit)):
            if args.secrets_file.endswith(".json"):
                secrets_file = args.secrets_file[:-5] + ".yaml"
                secrets_file = resolve_file_path(secrets_file, args.config_dir,
                                                 file_explicit=args.secrets_file_explicit,
                                                 directory_explicit=args.secrets_dir_explicit)
        if (not secrets_file) and args.secrets_file_explicit:
            error(f"Config secrets file not found: {args.config_file_explicit}")
        if not ensure_secrets_file_protected(secrets_file):
            warning(f"Your secrets file is not read protected from others: {secrets_file}")

    return config_file, secrets_file


def merge_config_and_secrets(config: dict, secrets: dict,
                             path_separator: str = DEFAULT_PATH_SEPARATOR) -> Tuple[dict, list, list]:
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


def path_basename(name: str, separator: str = DEFAULT_PATH_SEPARATOR) -> str:
    if (index := name.rfind(separator)) > 0:
        return name[index + 1:]
    return name


class Config:

    _PARENT = "@@@__PARENT__@@@"
    _MACRO_PATTERN = re.compile(r"\$\{([^}]+)\}")
    _MACRO_START = "${"
    _MACRO_END = "}"

    def __init__(self, file_or_dictionary: Union[str, dict],
                 path_separator: bool = DEFAULT_PATH_SEPARATOR, nomacros: bool = False) -> None:
        self._json = None
        self._path_separator = path_separator
        self._expand_macros = nomacros is not True
        # These booleans are effectively immutable; decided on this default/unchangable behavior.
        self._ignore_missing_macro = True
        self._stringize_non_primitive_types = True
        self._imap = {}
        self._load(file_or_dictionary)

    def lookup(self, name: str, config: Optional[dict] = None,
               allow_dictionary: bool = False, _macro_expansion: bool = False) -> Optional[str, dict]:

        def lookup_upwards(name: str, config: dict) -> Optional[str]:  # noqa
            nonlocal self
            if parent := self._get_parent(config):
                while parent:
                    if ((value := parent.get(name)) is not None) and Config._is_primitive_type(value):
                        return value
                    parent = self._get_parent(parent)
            return None

        if config is None:
            config = self._json
        value = None
        for index, name_component in enumerate(name_components := name.split(self._path_separator)):
            if value is not None:
                return None
            if not (name_component := name_component.strip()):
                continue
            if not (value := config.get(name_component)):
                # If this is not called during macro expansion (i.e. rather during lookup), and if this
                # is that last name_component, then look straight upwards/outwards in tree for a resolution.
                if (not _macro_expansion) and (index == (len(name_components) - 1)):
                    if (value := lookup_upwards(name_component, config)) is not None:
                        if Config._contains_macro(value):
                            # And if the value contains a macro try resolving from this context.
                            if macro_expanded_value := self._expand_macro_value(value, config):
                                # TODO: Maybe ore tricky stuff needed here.
                                return macro_expanded_value
                        return value
                return None
            if isinstance(value, dict):
                config = value
                value = None
        if value is not None:
            return value
        elif config and allow_dictionary:
            return self._cleanjson(config)
        return None

    def contains(self, name: str) -> bool:
        return self.lookup(name) is not None

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
                if self._file.endswith(".yaml") or self._file.endswith(".yml"):
                    self._json = yaml.safe_load(f)
                else:
                    self._json = json.load(f)
        if self._expand_macros:
            _ = self._macro_expand(self._json)

    def _macro_expand(self, data: dict) -> dict:
        for name in data:  # TODO: check for duplicate keys.
            if not ((name := name.strip()) and (not self._is_parent(name))):
                continue
            if isinstance(data[name], dict):
                self._set_parent(data[name], data)
                data[name] = self._macro_expand(data[name])
            elif not Config._is_primitive_type(data[name]) and not self._stringize_non_primitive_types:
                raise Exception(f"Non-primitive type found: {name}")
            else:
                data[name] = self._expand_macro_value(str(data[name]), data)

        return data

    def _lookup_macro_value(self, macro_name: str, data: dict) -> Optional[str]:
        if (macro_value := self.lookup(macro_name, data, _macro_expansion=True)) is not None:
            if Config._is_primitive_type(macro_value):
                return str(macro_value)
            return None
        data = self._get_parent(data)
        while data:
            if (macro_value := self.lookup(macro_name, data, _macro_expansion=True)) is not None:
                if Config._is_primitive_type(macro_value):
                    return str(macro_value)
                return None
            data = self._get_parent(data)
        return None

    def _expand_macro_value(self, value: str, data: dict) -> Optional[str]:
        expanding_macros = set()
        missing_macro_found = False
        original_simple_macros_to_retain = {}
        while True:
            if not (match := Config._MACRO_PATTERN.search(value)):
                break
            if (macro_name := match.group(1)) and (macro_value := self._lookup_macro_value(macro_name, data)):
                if Config._is_macro(macro_value):
                    original_simple_macros_to_retain[macro_value] = macro_name
                #
                # TODO: Notes from a failed attempt to support the below ... if not Config._is_macro(macro_value) ...
                # Maybe this original_simple_macros_to_retain scheme will work ... more testing required ...
                #
                # Note the _is_macro call above is a bit of a special case; if the macro we are expanding resolves
                # simply to another macro, then retain the original macro; this can be useful for this for example:
                #
                # foursight:
                #   SSH_TUNNEL_ES_NAME_PREFIX: ssh-tunnel-es-proxy
                #   SSH_TUNNEL_ES_NAME: ${SSH_TUNNEL_ES_NAME_PREFIX}-${SSH_TUNNEL_ES_ENV}-${SSH_TUNNEL_ES_PORT}
                #   SSH_TUNNEL_ES_ENV: ${AWS_PROFILE}
                #   4dn:
                #     AWS_PROFILE: 4dn
                #     SSH_TUNNEL_ES_ENV: ${AWS_PROFILE}-mastertest
                #     SSH_TUNNEL_ES_PORT: 9203
                #     dev:
                #       IDENTITY: whatever
                #   smaht:
                #     wolf:
                #       AWS_PROFILE: smaht-wolf
                #       SSH_TUNNEL_ES_PORT: 9209
                #       IDENTITY: whatever
                #
                # For lookup of foursight/smaht/wolf/SSH_TUNNEL_ES_NAME we will get ssh-tunnel-es-proxy-smaht-wolf-9209
                # as it takes the default foursight/SSH_TUNNEL_ES_ENV value which is foursight/smaht/wolf/AWS_PROFILE,
                # i.e. smaht-wolf; remember - we evaluate/expand the macro starting in the context of the lookup, i.e.
                # foursight/smaht/wolf. But for lookup of foursight/4dn/dev/SSH_TUNNEL_ES_NAME we want to (and do)
                # get ssh-tunnel-es-proxy-4dn-mastertest-9203 because retaining the ${SSH_TUNNEL_ES_ENV} in
                # foursight/SSH_TUNNEL_ES_NAME we will pick up the "overriding" foursight/4dn/SSH_TUNNEL_ES_ENV;
                # without this _is_macro call, we would get ssh-tunnel-es-proxy-4dn-9203 because ${SSH_TUNNEL_ES_ENV}
                # in foursight/SSH_TUNNEL_ES_NAME would have been expaned to ${AWS_PROFILE}.
                #
                if macro_name in expanding_macros:
                    raise Exception(f"Circular macro definition found: {macro_name}")
                expanding_macros.add(macro_name)
                value = value.replace(f"${{{macro_name}}}", macro_value)
            elif self._ignore_missing_macro:
                missing_macro_found = True
                # TODO: Use _MACRO_START/END ...
                value = value.replace(f"${{{macro_name}}}", f"@@@__[{macro_name}]__@@@")
            else:
                raise Exception(f"Macro name not found: {macro_name}")
        if missing_macro_found and self._ignore_missing_macro:
            # TODO: Use _MACRO_START/END ...
            value = value.replace("@@@__[", "${")
            value = value.replace("]__@@@", "}")
        if original_simple_macros_to_retain and self._contains_macro(value):
            for simple_macro in original_simple_macros_to_retain:
                original_simple_macro = original_simple_macros_to_retain[simple_macro]
                value = value.replace(simple_macro, f"{Config._MACRO_START}{original_simple_macro}{Config._MACRO_END}")
        return value

    def _get_parent(self, item: dict) -> Optional[dict]:
        return self._imap.get(item.get(Config._PARENT))

    def _set_parent(self, item: dict, parent: dict) -> None:
        parent_id = id(parent)
        self._imap[parent_id] = parent
        item[Config._PARENT] = parent_id

    def _is_parent(self, name: str) -> None:
        return name == Config._PARENT

    @staticmethod
    def _is_macro(value: str) -> bool:
        return value.startswith(Config._MACRO_START) and value.endswith(Config._MACRO_END)

    @staticmethod
    def _contains_macro(value: str) -> bool:
        if (index := value.find(Config._MACRO_START)) >= 0:
            if value[index + len(Config._MACRO_START):].find(Config._MACRO_END) > 0:
                return True
        return False

    @staticmethod
    def _is_primitive_type(value: Any) -> bool:  # noqa
        return isinstance(value, (int, float, str, bool))

    @staticmethod
    def _cleanjson(data: dict) -> dict:
        data = deepcopy(data)
        def remove_parent_properties(data: dict) -> dict:  # noqa
            if isinstance(data, dict):
                if Config._PARENT in data:
                    del data[Config._PARENT]
                for key, value in list(data.items()):
                    remove_parent_properties(value)
            return data
        return remove_parent_properties(data)


def get_version(package_name: str = "hms-utils") -> str:
    try:
        return get_package_version(package_name)
    except Exception:
        return ""


def warning(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr)


def error(message: str, usage: bool = False, status: int = 1,
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
