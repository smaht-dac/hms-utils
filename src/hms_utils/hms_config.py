# Convenience utility to maintain JSON based configuration properties.

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

    # TODO
    # After implementing the "import" thing I realized i *thjink* it could be generalized
    # such that secrets couild be treated like this rather than as treating them specially.

    config = None
    if args.config_file:
        try:
            config = Config(args.config_file,
                            config_imports=args.config_imports,
                            secrets_imports=args.secrets_imports,
                            path_separator=args.path_separator,
                            nomacros=args.nomacros, noaws=args.noaws)
        except Exception as e:
            error(f"Cannot process config file: {args.config_file}", exception=e, trace=True)

    secrets = None
    if args.secrets_file:
        try:
            secrets = Config(args.secrets_file,
                             path_separator=args.path_separator,
                             nomacros=args.nomacros, noaws=args.noaws)
        except Exception as e:
            error(f"Cannot process secrets file: {args.secrets_file}", exception=e, trace=True)

    merged_config = config.merge_secrets(secrets) if secrets else config

    if not args.names:
        if (not args.nomerge) and (not args.json) and (not args.yaml) and config and secrets:
            print_config_and_secrets_merged(merged_config, args)
        else:
            print_config_and_secrets_unmerged(config, secrets, args)
        exit(0)

    def setup_aws_profile_environment_variable():
        # TOTAL HACK (in a hurry 2024-10-08). This does what below args.exports
        # loop does but just for AWS_PROFILE environment variable setting.
        nonlocal args, merged_config
        for name in args.names:
            if (value := merged_config.lookup(name, allow_dictionary=True, raw=True)) is not None:
                if (name == AWS_PROFILE_ENV_NAME) and (AWS_PROFILE_ENV_NAME not in os.environ):
                    # Special case to handle list of paths the first of which specifies AWS_PROFILE,
                    # and which needs to be set to evaluate subsequent paths which are aws-secret macro values.
                    os.environ[AWS_PROFILE_ENV_NAME] = value
                # TODO: Refactor this increasingtly unwieldy logic.
                if isinstance(value, dict):
                    # Special case: If target name/path is a dictionary then generate
                    # exports for every direct (non-dictionary) key/value within it.
                    for key in value:
                        if ((single_value := value[key]) is not None) and (not isinstance(single_value, dict)):
                            if (key == AWS_PROFILE_ENV_NAME) and (AWS_PROFILE_ENV_NAME not in os.environ):
                                # Same special case as above for (direct) items within a dictionary.
                                os.environ[AWS_PROFILE_ENV_NAME] = single_value
                    if True:
                        # Walk up the hierarchy to get direct values of each parent/ancestor.
                        parent = value.parent
                        while parent:
                            for key in parent:
                                if ((single_value := parent[key]) is not None) and (not isinstance(single_value, dict)):
                                    if (key == AWS_PROFILE_ENV_NAME) and (AWS_PROFILE_ENV_NAME not in os.environ):
                                        os.environ[AWS_PROFILE_ENV_NAME] = single_value
                            parent = parent.parent

    status = 0
    if args.export:
        if args.export_file and os.path.exists(args.export_file):
            error(f"Export file must not already exist: {args.export_file}")
        exports = {}
        setup_aws_profile_environment_variable()
        for name in args.names:
            if (colon := name.find(DEFAULT_EXPORT_NAME_SEPARATOR)) > 0:
                export_name = name[0:colon]
                if not (name := name[colon + 1:].strip()):
                    continue
            else:
                export_name = path_basename(name, args.path_separator)
            found = False ; found_dictionary = False  # noqa
            if (value := merged_config.lookup(name, allow_dictionary=True, raw=True)) is not None:
                if (export_name == AWS_PROFILE_ENV_NAME) and (AWS_PROFILE_ENV_NAME not in os.environ):
                    # Special case to handle list of paths the first of which specifies AWS_PROFILE,
                    # and which needs to be set to evaluate subsequent paths which are aws-secret macro values.
                    os.environ[AWS_PROFILE_ENV_NAME] = value
                # TODO: Refactor this increasingtly unwieldy logic.
                if isinstance(value, dict):
                    # Special case: If target name/path is a dictionary then generate
                    # exports for every direct (non-dictionary) key/value within it.
                    found_dictionary = True
                    for key in value:
                        if ((single_value := value[key]) is not None) and (not isinstance(single_value, dict)):
                            if (key == AWS_PROFILE_ENV_NAME) and (AWS_PROFILE_ENV_NAME not in os.environ):
                                # Same special case as above for (direct) items within a dictionary.
                                os.environ[AWS_PROFILE_ENV_NAME] = single_value
                            # TODO: A bit shaky on this ...
                            if merged_config._contains_macro(single_value):
                                single_value = merged_config._expand_macro_value(single_value, value)
                            # TODO: A bit shaky on this ...
                            if merged_config._contains_aws_secret_macro(single_value):
                                # Note the trailing separator/slash on the context.
                                aws_secret_context_path = f"{name}{args.path_separator}"
                                single_value = config._expand_aws_secret_macros(
                                    single_value, aws_secret_context_path=aws_secret_context_path)
                            exports[key] = single_value
                            found = True
                    if True:
                        # Walk up the hierarchy to get direct values of each parent/ancestor.
                        parent = value.parent
                        while parent:
                            for key in parent:
                                if ((single_value := parent[key]) is not None) and (not isinstance(single_value, dict)):
                                    if (key == AWS_PROFILE_ENV_NAME) and (AWS_PROFILE_ENV_NAME not in os.environ):
                                        os.environ[AWS_PROFILE_ENV_NAME] = single_value
                                    # TODO: Shaky on this ...
                                    if merged_config._contains_macro(single_value):
                                        single_value = merged_config._expand_macro_value(single_value, value)
                                    # TODO: Shaky on this ...
                                    if merged_config._contains_aws_secret_macro(single_value):
                                        # Note the trailing separator/slash on the context.
                                        aws_secret_context_path = f"{name}{args.path_separator}"
                                        single_value = config._expand_aws_secret_macros(
                                            single_value, aws_secret_context_path=aws_secret_context_path)
                                    if key not in exports:
                                        exports[key] = single_value
                            parent = parent.parent
                else:
                    exports[export_name] = value
                    found = True
            if not found:
                if args.nowarning:
                    if found_dictionary:
                        warning(f"{chars.rarrow} Config name/path contains no direct values: {name}")
                    else:
                        warning(f"{chars.rarrow} Config name/path not found: {name}")
                status = 1
        exports = dict(sorted(exports.items()))
        if args.export_file:
            if args.verbose:
                print(f"Writing exports to file: {args.export_file}")
            with io.open(args.export_file, "w") as f:
                for export in exports:
                    export = f"export {export}={exports[export]}"
                    if args.verbose:
                        print(f"{chars.rarrow_hollow} {export}")
                    f.write(f"{export}\n")
        else:
            for export in sorted(exports):
                export = f"export {export}={exports[export]}"
                print(export)
    else:
        for name in args.names:
            if merged_config and ((value := merged_config.lookup(
                                            name, allow_dictionary=args.json,
                                            aws_secret_context_path=args.aws_secret_context_path)) is not None):
                if args.json_formatted and isinstance(value, dict):
                    print(json.dumps(value, indent=4))
                else:
                    if args.verbose:
                        print(f"{name}: {value}")
                    else:
                        print(value)
            else:
                if not args.nowarning:
                    warning(f"Cannot find name/path: {name}")
                status = 1

    sys.exit(status)


def main_show_script_path():
    sys.argv = ["hmx-config", "--functions"]
    main()


def parse_args(argv: List[str]) -> object:

    class Args:
        config_dir = os.path.expanduser(DEFAULT_CONFIG_DIR)
        config_dir_explicit = False
        config_file = DEFAULT_CONFIG_FILE_NAME
        config_file_explicit = False
        config_imports = []
        import_config_files = []
        secrets_file = DEFAULT_SECRETS_FILE_NAME
        secrets_file_explicit = False
        secrets_imports = []
        aws_secret_context_path = None
        import_secrets_files = []
        path_separator = DEFAULT_PATH_SEPARATOR
        name = None
        names = []
        list = False
        yaml = False
        json = False
        json_formatted = False
        json_only = False
        raw = False
        show_secrets = False
        show_paths = False
        nocolor = False
        nomerge = False
        nosort = False
        nomacros = False
        export = False
        export_file = None
        noaws = False
        verbose = False
        nowarning = False
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
            args.config_file = arg
            args.config_file_explicit = True
            argi += 1
        elif arg in ["--secrets-config", "-secrets-config", "--secrets-conf", "-secrets-conf", "--secret-config",
                     "-secret-config", "--secret-conf", "-secret-conf", "--secrets", "-secrets", "--secret", "-secret"]:
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                _usage()
            args.secrets_file = arg
            args.secrets_file_explicit = True
            argi += 1
        elif arg in ["--imports", "-imports", "--import", "-import"]:
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                _usage()
            if "secret" in args.lower():
                args.import_secret_files.append(arg)
            else:
                args.import_config_files.append(arg)
            argi += 1
        elif arg in ["--import-config", "-import-config", "--import-conf", "-import-conf",
                     "--iconfig", "-iconfig", "--iconf", "-iconf"]:
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                _usage()
            args.import_config_files.append(arg)
            argi += 1
        elif arg in ["--import-secrets", "-import-secrets", "--import-secret", "-import-secret",
                     "--isecrets", "-isecrets", "--isecret", "-isecret"]:
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                _usage()
            args.import_secrets_files.append(arg)
            argi += 1
        elif arg in ["--context", "-context"]:
            if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                _usage()
            args.aws_secret_context_path = arg
            argi += 1
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
        elif arg in ["--json-only", "-json-only", "--jsononly", "-jsononly"]:
            args.json = True
            args.json_only = True
        elif arg in ["--jsonf", "-jsonf", "--json-formatted", "-json-formatted", "--json-format", "-json-format"]:
            args.json = True
            args.json_formatted = True
        elif arg in ["--raw", "-raw"]:
            args.raw = True
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
        elif arg in ["-noaws", "noaws"]:
            args.noaws = True
        elif arg in ["--debug", "-debug"]:
            args.debug = True
        elif arg in ["--nowarning", "-nowarning", "--nowarnings", "-nowarnings"]:
            args.nowarning = True
        elif arg in ["--verbose", "-verbose"]:
            args.verbose = True
        elif arg in ["--version", "-version"]:
            print(f"hmx-utils version: {get_version()}")
            exit(0)
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

    # TODO: Refactor with other file resolution code; and with yaml support etc.
    for import_config_file in args.import_config_files:
        if import_config_file.lower() == "default":
            import_config_file = args.config_file or DEFAULT_CONFIG_FILE_NAME
        import_config_file = resolve_file_path(import_config_file, args.config_dir, file_explicit=True,
                                               directory_explicit=args.config_dir_explicit)
        if not import_config_file:
            error(f"Cannot open (import) config file: {import_config_file}")
        try:
            with io.open(import_config_file) as f:
                if import_config_file.startswith(".yaml") or import_config_file.startswith(".yml"):
                    config_import_json = JSON(yaml.safe_load(f))
                else:
                    config_import_json = JSON(json.load(f))
        except Exception:
            error(f"Cannot load (import) config file: {import_config_file}")
        args.config_imports.append(config_import_json)

    for import_secrets_file in args.import_secrets_files:
        if import_secrets_file.lower() == "default":
            import_secrets_file = args.secrets_file or DEFAULT_SECRETS_FILE_NAME
        import_secrets_file = resolve_file_path(import_secrets_file, args.config_dir, file_explicit=True,
                                                directory_explicit=args.config_dir_explicit)
        if not os.path.exists(import_secrets_file):
            error(f"Cannot open (import) secrets file: {import_secrets_file}")
        try:
            with io.open(import_secrets_file) as f:
                if import_secrets_file.startswith(".yaml") or import_secrets_file.startswith(".yml"):
                    secrets_import_json = yaml.safe_load(f)
                else:
                    secrets_import_json = JSON(json.load(f))
        except Exception:
            error(f"Cannot load (import) secrets file: {import_secrets_file}")
        args.secrets_imports.append(secrets_import_json)

    return args


# def tree_key_modifier(secrets: Config, args: object, key_path: str, key: Optional[str] = None) -> Optional[str]:
#     return ((key or key_path) if ((not secrets) or (secrets.lookup(key_path) is None))
#             else color(key or key_path, "red", nocolor=args.nocolor))


# def tree_value_modifier(secrets: Config, args: object, key_path: str, value: str) -> Optional[str]:
#     if (not args.show_secrets) and secrets and secrets.contains(key_path):
#         value = OBFUSCATED_VALUE
#     return value if ((not secrets) or
#                      (secrets.lookup(key_path) is None)) else color(value, "red", nocolor=args.nocolor)


def print_config_and_secrets_merged(merged_config: Config, args: object) -> None:

    global SUPPRESS_AWS_SECRET_NOT_FOUND_WARNING
    SUPPRESS_AWS_SECRET_NOT_FOUND_WARNING = True
    merged_config_json = merged_config.json
    secrets = merged_config.secrets if hasattr(merged_config, "secrets") else None
    unmerged_secrets = merged_config.unmerged_secrets if hasattr(merged_config, "unmerged_secrets") else None
    merged_secrets = merged_config.merged_secrets if hasattr(merged_config, "merged_secrets") else None

    def tree_key_modifier(key_path: str, key: Optional[str] = None) -> Optional[str]:
        nonlocal args, secrets
        return ((key or key_path) if ((not secrets) or (not secrets.contains(key_path)))
                else color(key or key_path, "red", nocolor=args.nocolor))

    def tree_value_modifier(key_path: str, value: str) -> Optional[str]:
        nonlocal args, secrets
        if (not args.show_secrets) and secrets and secrets.contains(key_path):
            value = OBFUSCATED_VALUE
        return value if ((not secrets) or
                         (not secrets.contains(key_path))) else color(value, "red", nocolor=args.nocolor)

    def tree_value_annotator(key_path: str) -> Optional[str]:
        nonlocal unmerged_secrets
        if unmerged_secrets and (key_path in unmerged_secrets):
            return f"{chars.rarrow} unmerged {chars.xmark}"
        return None

    def tree_value_annotator_secrets(key_path: str) -> Optional[str]:
        nonlocal merged_secrets, unmerged_secrets
        if unmerged_secrets and (key_path in unmerged_secrets):
            return f"{chars.rarrow} unmerged {chars.xmark}"
        elif merged_secrets and (key_path in merged_secrets):
            return f"{chars.rarrow_hollow} merged {chars.check}"
        return None

    def tree_arrow_indicator(key_path: str, value: Any) -> str:
        nonlocal secrets
        return chars.rarrow_hollow if (secrets and secrets.contains(key_path)) else ""

    if merged_config and secrets:
        if not args.nosort:
            merged_config_json = sort_dictionary(merged_config_json)
        print(f"\n{merged_config.file}: [with {os.path.basename(args.secrets_file)}"
              f"{' partially' if unmerged_secrets else ''} merged in]")
        if args.list:
            print_dictionary_list(merged_config_json, path_separator=args.path_separator,
                                  prefix=f" {chars.rarrow_hollow} ",
                                  key_modifier=tree_key_modifier,
                                  value_modifier=tree_value_modifier,
                                  value_annotator=tree_value_annotator)
        else:
            print_dictionary_tree(merged_config_json, indent=1, paths=args.show_paths,
                                  path_separator=args.path_separator,
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
    SUPPRESS_AWS_SECRET_NOT_FOUND_WARNING = False


def print_config_and_secrets_unmerged(config: Config, secrets: Config, args: object) -> None:

    secrets_imports = config.secrets_imports

    def tree_key_modifier(key_path: str, key: Optional[str] = None) -> Optional[str]:
        nonlocal args, secrets, secrets_imports
        secret = False
        if key_path:
            if secrets and secrets.contains(key_path):
                secret = True
        return color(key or key_path, "red", nocolor=args.nocolor) if secret else (key or key_path)

    def tree_value_modifier(key_path: str, value: str) -> Optional[str]:
        nonlocal args, secrets
        if (not args.show_secrets) and secrets and secrets.contains(key_path):
            value = OBFUSCATED_VALUE
        return value if ((not secrets) or
                         (not secrets.contains(key_path))) else color(value, "red", nocolor=args.nocolor)

    if config:
        if not args.json_only:
            print(f"\n{config.file}:")
        data = config.json if not (args.debug or args.raw) else config.rawjson
        if not args.nosort:
            data = sort_dictionary(data)
        if args.yaml:
            print(yaml.dump(data))
        elif args.json:
            if True:  # TODO: This seem very dicey; added for 4dn-cloud-infra secrets.json generation.
                for key in data:
                    if Config._is_primitive_type(value := data[key]) and config._contains_aws_secret_macro(value):
                        if (value := config._expand_aws_secret_macros(value, aws_secret_context_path=None)) is not None:
                            data[key] = value
            print(json.dumps(data, indent=4))
        elif args.list:
            print_dictionary_list(data, path_separator=args.path_separator, prefix=f" {chars.rarrow_hollow} ")
        else:
            print_dictionary_tree(data, indent=1, paths=args.show_paths, path_separator=args.path_separator,
                                  key_modifier=tree_key_modifier,
                                  value_modifier=tree_value_modifier)
    if secrets:
        if not args.json_only:
            print(f"\n{secrets.file}:")
        data = secrets.json if not (args.debug or args.raw) else secrets.rawjson
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
    if not args.json_only:
        print()


def resolve_files(args: List[str]) -> Tuple[Optional[str], Optional[str]]:

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
                                                 directory_explicit=args.config_dir_explicit)
        if (not secrets_file) and args.secrets_file_explicit:
            error(f"Config secrets file not found: {args.config_file_explicit}")
        if not ensure_secrets_file_protected(secrets_file):
            warning(f"Your secrets file is not read protected from others: {secrets_file}")

    return config_file, secrets_file


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


def path_basename(name: str, separator: str = DEFAULT_PATH_SEPARATOR) -> str:
    if (index := name.rfind(separator)) > 0:
        return name[index + 1:]
    return name


class Config:

    _MACRO_START = "${"
    _MACRO_END = "}"
    _MACRO_PATTERN = re.compile(r"\$\{([^}]+)\}")
    _MACRO_HIDE_START = "@@@__["
    _MACRO_HIDE_END = "]__@@@"
    _MACRO_PATTERN = re.compile(r"\$\{([^}]+)\}")
    _AWS_SECRET_MACRO_NAME_PREFIX = "aws-secret:"
    _AWS_SECRET_MACRO_START = f"{_MACRO_START}{_AWS_SECRET_MACRO_NAME_PREFIX}"
    _AWS_SECRET_MACRO_END = _MACRO_END
    _AWS_SECRET_MACRO_PATTERN = re.compile(r"\$\{aws-secret:([^}]+)\}")
    _AWS_SECRET_NAME_NAME = "IDENTITY"
    _IMPORTED_CONFIG_KEY_PREFIX = "@@@__CONFIG__:"
    _IMPORTED_SECRETS_KEY_PREFIX = "@@@__SECRETS__:"

    def __init__(self, file_or_dictionary: Union[str, dict],
                 config_imports: List[dict] = [], secrets_imports: List[dict] = [],
                 path_separator: str = DEFAULT_PATH_SEPARATOR, nomacros: bool = False, noaws: bool = False) -> None:
        self._json = JSON()
        self._path_separator = path_separator
        self._expand_macros = not nomacros
        self.secrets = None
        self.merged_secrets = None
        self.unmerged_secrets = None
        self._config_imports = config_imports
        self._secrets_imports = secrets_imports
        self._noaws = noaws
        # These booleans are effectively immutable; decided on this default/unchangable behavior.
        self._ignore_missing_macro = True
        self._stringize_non_primitive_types = True
        self._loading = True
        self._load(file_or_dictionary)
        self._loading = False

    def merge_secrets(self, secrets: Config) -> Config:
        merged_config_json, merged_secretst, unmerged_secretst = (
            Config._merge_config_and_secrets(self.json, secrets.json, path_separator=self._path_separator))
        merged_config = Config(merged_config_json, noaws=self._noaws)
        merged_config._file = self.file
        merged_config.secrets = secrets
        merged_config.merged_secrets = merged_secretst
        merged_config.unmerged_secrets = unmerged_secretst
        return merged_config

    def lookup(self, name: str, config: Optional[dict] = None,
               allow_dictionary: bool = False, aws_secret_context_path: Optional[str] = None,
               noaws: bool = False, raw: bool = False, _search_imports: bool = True) -> Optional[str, dict]:

        def lookup_upwards(name: str, config: dict) -> Optional[str]:  # noqa
            nonlocal self
            if parent := config.parent:
                while parent:
                    if ((value := parent.get(name)) is not None) and Config._is_primitive_type(value):
                        return value
                    parent = parent.parent
            return None

        if config is None:
            config = self._json
        value = None
        for index, name_component in enumerate(name_components := name.split(self._path_separator)):
            if value is not None:
                return None  # TODO: Why was this here and what could it mean?
            if not (name_component := name_component.strip()):
                continue
            if not (value := config.get(name_component)):
                # If this is not called during macro expansion (i.e. rather during lookup), and if this
                # is that last name_component, then look straight upwards/outwards in tree for a resolution.
                if (not self._loading) and (index == (len(name_components) - 1)):
                    if (value := lookup_upwards(name_component, config)) is not None:
                        if Config._contains_macro(value):
                            # And if the value contains a macro try resolving from this context.
                            if macro_expanded_value := self._expand_macro_value(value, config):
                                # TODO: Maybe ore tricky stuff needed here.
                                if self._contains_aws_secret_macro(value):
                                    return self._expand_aws_secret_macros(
                                               macro_expanded_value,
                                               aws_secret_context_path=aws_secret_context_path or name, noaws=noaws)
                                return macro_expanded_value
                        return value
                if _search_imports and (docs := self.imports):
                    for doc in docs:
                        if (value := self.lookup(name, doc, _search_imports=False)) is not None:
                            if isinstance(value, dict) and (not allow_dictionary):
                                return None
                            return value
                return None
            if isinstance(value, dict):
                config = value
                value = None
        if value is not None:
            if not self._loading:
                if self._contains_aws_secret_macro(value):
                    return self._expand_aws_secret_macros(value,
                                                          aws_secret_context_path=aws_secret_context_path or name,
                                                          noaws=noaws)
            return value
        elif config and allow_dictionary:
            return config if raw else self._cleanjson(config)
        return None

    @property
    def imports(self) -> List[dict]:
        imports = []
        for key in self._json:
            if (key.startswith(Config._IMPORTED_CONFIG_KEY_PREFIX) or
                key.startswith(Config._IMPORTED_SECRETS_KEY_PREFIX)) and isinstance(self._json[key], dict):  # noqa
                imports.append(self._json[key])
        return imports

    @property
    def secrets_imports(self) -> List[dict]:
        imports = []
        for key in self._json:
            if key.startswith(Config._IMPORTED_SECRETS_KEY_PREFIX) and isinstance(self._json[key], dict):  # noqa
                imports.append(self._json[key])
        return imports

    def contains(self, name: str) -> bool:
        return self.lookup(name, noaws=True) is not None

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
            self._json = JSON(file_or_dictionary)
            self._file = None
        else:
            self._file = file_or_dictionary
            with io.open(file_or_dictionary, "r") as f:
                if self._file.endswith(".yaml") or self._file.endswith(".yml"):
                    self._json = JSON(yaml.safe_load(f))
                else:
                    self._json = JSON(json.load(f))
        for config_import in self._config_imports:
            self._import_config(config_import)
        for secrets_import in self._secrets_imports:
            self._import_secrets(secrets_import)
        if self._expand_macros:
            _ = self._macro_expand(self._json)

    @staticmethod
    def _merge_config_and_secrets(config: JSON, secrets: JSON,
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

    def _macro_expand(self, data: dict) -> dict:
        for name in data:  # TODO: check for duplicate keys.
            if not (name := name.strip()):
                continue
            if isinstance(data[name], dict):
                data[name] = self._macro_expand(data[name])
            elif not Config._is_primitive_type(data[name]) and not self._stringize_non_primitive_types:
                raise Exception(f"Non-primitive type found: {name}")
            else:
                data[name] = self._expand_macro_value(str(data[name]), data)

        return data

    def _lookup_macro_value(self, macro_name: str, data: dict) -> Optional[str]:
        if (macro_value := self.lookup(macro_name, data)) is not None:
            if Config._is_primitive_type(macro_value):
                return str(macro_value)
            return None
        data = data.parent
        while data:
            if (macro_value := self.lookup(macro_name, data)) is not None:
                if Config._is_primitive_type(macro_value):
                    return str(macro_value)
                return None
            data = data.parent
        return None

    def _expand_macro_value(self, value: str, data: dict) -> Optional[str]:
        expanding_macros = set()
        missing_macro_found = False
        original_simple_macros_to_retain = {}
        while True:
            if not (match := Config._MACRO_PATTERN.search(value)):
                break
            if (macro_name := match.group(1)) and (macro_value := self._lookup_macro_value(macro_name, data)):
                if Config._is_macro(macro_value) and (not self._is_aws_secret_macro(macro_value)):
                    original_simple_macros_to_retain[macro_value] = macro_name
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
                value = value.replace(f"{Config._MACRO_START}{macro_name}{Config._MACRO_END}",
                                      f"{Config._MACRO_HIDE_START}{macro_name}{Config._MACRO_HIDE_END}")
            else:
                raise Exception(f"Macro name not found: {macro_name}")
        if missing_macro_found and self._ignore_missing_macro:
            value = value.replace(Config._MACRO_HIDE_START, Config._MACRO_START)
            value = value.replace(Config._MACRO_HIDE_END, Config._MACRO_END)
        if original_simple_macros_to_retain and self._contains_macro(value):
            for simple_macro in original_simple_macros_to_retain:
                original_simple_macro = original_simple_macros_to_retain[simple_macro]
                value = value.replace(simple_macro, f"{Config._MACRO_START}{original_simple_macro}{Config._MACRO_END}")
        return value

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
    def _is_aws_secret_macro_name(macro_name: str) -> bool:
        return macro_name.startswith(Config._AWS_SECRET_MACRO_NAME_PREFIX)

    @staticmethod
    def _is_aws_secret_macro(macro: str) -> bool:
        return (macro.startswith(Config._AWS_SECRET_MACRO_START) and
                macro.endswith(Config._AWS_SECRET_MACRO_END))

    @staticmethod
    def _contains_aws_secret_macro(value: str) -> bool:
        if (index := value.find(Config._AWS_SECRET_MACRO_START)) >= 0:
            if value[index + len(Config._AWS_SECRET_MACRO_START):].find(Config._AWS_SECRET_MACRO_END) > 0:
                return True
        return False

    def _expand_aws_secret_macros(self, value: str, aws_secret_context_path: str, noaws: bool = False) -> Optional[str]:
        while ((match := Config._AWS_SECRET_MACRO_PATTERN.search(value)) and
               (secret_specifier := match.group(1))):
            if macro_value := self._expand_aws_secret_macro(secret_specifier, aws_secret_context_path, noaws=noaws):
                macro = f"{Config._AWS_SECRET_MACRO_START}{secret_specifier}{Config._AWS_SECRET_MACRO_END}"
                value = value.replace(macro, macro_value)
            else:
                # Hide the macro temporarily for this loop.
                value = value.replace(f"{Config._AWS_SECRET_MACRO_START}{secret_specifier}{Config._MACRO_END}",
                                      f"{Config._MACRO_HIDE_START}{secret_specifier}{Config._MACRO_HIDE_END}")
        # Unhide unfound macros.
        value = value.replace(Config._MACRO_HIDE_START, Config._AWS_SECRET_MACRO_START)
        value = value.replace(Config._MACRO_HIDE_END, Config._MACRO_END)
        return value

    def _expand_aws_secret_macro(self, secret_specifier: str,
                                 aws_secret_context_path: str, noaws: bool = False) -> Optional[str]:
        if (index := secret_specifier.find(self._path_separator)) > 0:
            secret_name = secret_specifier[index + 1:]
            secrets_name = secret_specifier[0:index]
        else:
            secret_name = secret_specifier
            secrets_name = None
            if (index := aws_secret_context_path.rfind(self._path_separator)) > 0:
                aws_secret_context_path = aws_secret_context_path[:index]
                secrets_name_path = f"{aws_secret_context_path}/{Config._AWS_SECRET_NAME_NAME}"
                secrets_name = self.lookup(secrets_name_path)
        if secrets_name and secret_name:
            if secret_value := self._lookup_aws_secret(secrets_name, secret_name, noaws=noaws):
                return secret_value
        return None

    @lru_cache(maxsize=64)
    def _lookup_aws_secret(self, secrets_name: str, secret_name: str, noaws: bool = False) -> Optional[str]:
        if noaws or self._noaws:
            return "__noaws__"
        try:
            if secrets := self._aws_get_secret_value(secrets_name):
                return secrets.get(secret_name)
        except Exception:
            global SUPPRESS_AWS_SECRET_NOT_FOUND_WARNING
            if not SUPPRESS_AWS_SECRET_NOT_FOUND_WARNING:
                warning(f"Cannot find AWS secret: {secrets_name}/{secret_name}")
            return None

    def _aws_get_secret_value(self, secrets_name: str) -> Optional[dict]:
        boto_secrets = BotoClient("secretsmanager")
        if secrets := boto_secrets.get_secret_value(SecretId=secrets_name):
            return json.loads(secrets.get("SecretString"))

    def _import_config(self, config: dict, name: Optional[str] = None) -> None:
        if isinstance(config, dict) and config:
            self._json[f"{Config._IMPORTED_CONFIG_KEY_PREFIX}{name or ''}"] = config

    def _import_secrets(self, secrets: dict, name: Optional[str] = None) -> None:
        if isinstance(secrets, dict) and secrets:
            self._json[f"{Config._IMPORTED_SECRETS_KEY_PREFIX}{name or ''}"] = secrets

    @staticmethod
    def _is_primitive_type(value: Any) -> bool:  # noqa
        return isinstance(value, (int, float, str, bool))

    @staticmethod
    def _cleanjson(data: dict) -> dict:
        data = deepcopy(data)
        def remove_imported_configs(data: dict) -> None:  # noqa
            todelete = []
            for key in data:
                if (key.startswith(Config._IMPORTED_CONFIG_KEY_PREFIX) or
                    key.startswith(Config._IMPORTED_SECRETS_KEY_PREFIX)):  # noqa
                    todelete.append(key)
            for key in todelete:
                del data[key]
        remove_imported_configs(data)
        return data


def warning(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr, flush=True)


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
    print(f"{chars.rarrow} hmx-config reads named value from {DEFAULT_CONFIG_FILE_NAME} or"
          f" {DEFAULT_SECRETS_FILE_NAME} in: {DEFAULT_CONFIG_DIR}")
    print(f"  {chars.rarrow_hollow} usage: python hms_config.py"
          f" [ path/name [-json] | [-nocolor | -nomerge | -nosort | -json | -yaml | -show] ]")
    sys.exit(1)


if __name__ == "__main__":
    main()
