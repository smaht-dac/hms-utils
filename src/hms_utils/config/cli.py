from __future__ import annotations
import io
import json
import os
import sys
import traceback
from typing import List, Optional
import yaml
from hms_utils.chars import chars
from hms_utils.config.config import Config
from hms_utils.config.config_output import ConfigOutput
from hms_utils.config.config_with_aws_macros import ConfigWithAwsMacros
from hms_utils.crypto_utils import read_encrypted_file
from hms_utils.version_utils import get_version
from hms_utils.dictionary_parented import JSON
from hms_utils.path_utils import is_current_or_parent_relative_path

DEFAULT_CONFIG_DIR = "~/.config/hms"
DEFAULT_CONFIG_FILE_NAME = "config.json"
DEFAULT_SECRETS_FILE_NAME = "secrets.json"
DEFAULT_PATH_SEPARATOR = "/"
OBFUSCATED_VALUE = "********"


def main(argv: Optional[List] = None):

    args = parse_args(argv if isinstance(argv, list) else sys.argv[1:])

    config = args.config
    merged_paths, unmerged_paths = config.merge(args.configs_for_merge)
    config.include(args.configs_for_include)

    if args.noaws:
        config._noaws = True

    if not args.lookup_paths and (args.tree or args.list or args.dump):
        if config.name:
            print(f"{chars.rarrow} {config.name}")
        if args.configs_for_merge:
            for config_for_merge in args.configs_for_merge:
                if config_for_merge.name:
                    print(f"{chars.rarrow_hollow} {config_for_merge.name} (merged)")
        if args.configs_for_include:
            for config_for_include in args.configs_for_include:
                if config_for_include.name:
                    print(f"{chars.rarrow_hollow} {config_for_include.name} (included)")

    if not args.lookup_paths:
        if args.json:
            data = config.lookup("/", show=args.show).sorted()
            print(json.dumps(data, indent=4 if args.formatted else None))
        elif args.tree:
            ConfigOutput.print_tree(config, show=args.show, nocolor=args.nocolor)
        elif args.list:
            ConfigOutput.print_list(config, show=args.show, nocolor=args.nocolor)
        elif args.dump:
            config._dump_for_testing(sorted=not args.raw, verbose=args.verbose, check=args.check)

    status = 0
    if args.lookup_paths:
        if args.exports:
            status = handle_exports_command(config, args)
        else:
            status = handle_lookup_command(config, args)

    if config._warnings:
        # if ((not args.nowarnings) and args.lookup_paths) or args.warnings:
        if args.warnings:
            print(f"{chars.rarrow} WARNINGS ({len(config._warnings)}):", file=sys.stderr)
            for warning in config._warnings:
                print(f"  {chars.rarrow_hollow} {warning}", file=sys.stderr)

    sys.exit(status)


def main_show_script_path():
    sys.argv = ["hmsconfig", "--functions"]
    main()


def handle_lookup_command(config: Config, args: object) -> int:
    if not args.lookup_paths:
        return 0
    status = 0 ; n = 0  # noqa
    for lookup_path in args.lookup_paths:
        if (value := config.lookup(lookup_path, show=args.show)) is None:
            status = 1
            if not args.verbose:
                continue
            value = chars.null
        if args.show and Config._contains_macro(value):
            status = 1
        if isinstance(value, JSON):
            if lookup_path.endswith(config.path_separator):
                if inherited_values := config.lookup_inherited_values(value, show=args.show):
                    for inherited_value_key in inherited_values:
                        if inherited_value_key not in value:
                            value[inherited_value_key] = inherited_values[inherited_value_key]
            if args.json and args.formatted:
                value = json.dumps(value.sorted(), indent=4)
            elif args.tree:
                prefix = "...\n" if args.verbose else ("" if n == 0 else "\n")
                value = (prefix +
                         ConfigOutput.print_tree(config, data=value.sorted(), nocolor=args.nocolor,
                                                 string=True, indent=2 if args.verbose else None, show=args.show))
        if args.verbose:
            print(f"{lookup_path}: {value}")
        else:
            print(f"{value}")
        n += 1
    return status


def handle_exports_command(config: Config, args: object) -> int:
    exports, status = config.exports(args.lookup_paths, show=args.show)
    for export_key in exports:
        if Config._contains_macro(exports[export_key]):
            status = 1
            break
    if args.exports_file:
        if os.path.exists(args.exports_file):
            _error(f"Export file must not already exist: {args.exports_file}")
        with io.open(args.exports_file, "w") as f:
            for export in exports:
                export = f"export {export}={exports[export]}"
                f.write(f"{export}\n")
                if args.verbose:
                    print(f"{chars.rarrow_hollow} {export}")
    else:
        if args.json:
            print(json.dumps(exports, indent=4 if args.formatted else None))
        else:
            for export in sorted(exports):
                export = f"export {export}={exports[export]}"
                print(export)
    return status


def parse_args(argv: List[str]) -> object:

    class Args:
        config_dir = None
        config = None
        configs_for_merge = []
        configs_for_include = []
        lookup_paths = []
        json = False
        exports = False
        exports_file = None
        tree = False
        list = False
        files = False
        dump = False
        raw = False
        check = False
        show = False
        noaws = False
        nocolor = False
        formatted = False
        verbose = False
        password = False
        nowarnings = False
        warnings = False
        debug = False

    args = Args()

    def get_configs(_merges: bool = False, _includes: bool = False) -> None:

        nonlocal argv, args

        # We allow one or more files to be listed after --config or --secrets. Only the first file
        # in the list may NOT end in a ".json" suffix (as a argument not end in that, or and argument
        # starting with a dash, signifies the and of this list). If a file name contains "secret",
        # or is prepended with a special "secret:" or "secrets:" prefix, or if it is listed afer
        # the --secrets option, then it is assumed to contain secrets, which is really just ensures
        # that the values therein won't displayed by default when listing the contents of the file.
        # Multiple --config or --secrets options can be used; so you have lots of options option-wise.

        # If and only if either of the the --config or --secrets options are given then the
        # default config/secrets file (e.g. i.e. in  the ~/.config/hms directory) will NOT be used.

        def read_file(file: str) -> Optional[dict]:
            try:
                if data := read_encrypted_file(file, password=args.password):
                    if file.endswith(".yaml") or config_file.endswith(".yml"):
                        data = yaml.safe_load(data)
                    else:
                        data = json.loads(data)
            except Exception:
                with io.open(file, "r") as f:
                    if file.endswith(".yaml") or file.endswith(".yml"):
                        data = yaml.safe_load(f)
                    else:
                        data = json.load(f)
            return data

        def get_config_dir() -> None:
            nonlocal argv, args
            get_password_arg()
            config_dir = os.path.expanduser(DEFAULT_CONFIG_DIR)
            if value := os.environ.get("HMS_CONFIG_DIR"):
                config_dir = value
            argi = 0 ; argn = len(argv)  # noqa
            while argi < argn:
                arg = argv[argi] ; argi += 1  # noqa
                if arg in ["--dir", "-dir", "--directory", "-directory"]:
                    if not ((argi < argn) and (config_dir := argv[argi])):
                        _usage()
                    del argv[argi - 1:argi + 1]
                    break
            if not config_dir:
                return None
            if not os.path.isabs(config_dir):
                config_dir = os.path.normpath(os.path.join(os.getcwd(), config_dir))
            if not os.path.isdir(config_dir := os.path.normpath(config_dir)):
                _error(f"Configuration directory does not exist: {config_dir}")
            args.config_dir = config_dir

        def verify_config(config_file: str, config_dir: str, secrets: bool = False) -> Config:  # noqa
            if not secrets:
                if config_file.startswith("secret:"):
                    secrets = True
                    config_file = config_file[len("secret:"):]
                elif config_file.startswith("secrets:"):
                    secrets = True
                    config_file = config_file[len("secrets:"):]
                elif "secret" in config_file.lower():
                    secrets = True
            config_file = os.path.expanduser(config_file)
            if os.path.isabs(config_file):
                config_file = os.path.normpath(config_file)
            elif is_current_or_parent_relative_path(config_file) and os.path.isfile(config_file):
                config_file = os.path.normpath(os.path.join(os.getcwd(), config_file))
            elif os.path.isfile(file := os.path.normpath(os.path.join(config_dir, config_file))):
                config_file = file
            else:
                config_file = os.path.normpath(os.path.join(os.getcwd(), config_file))
            if not os.path.isfile(config_file):
                _error(f"Configuration file does not exist: {config_file}")
            try:
                config_json = read_file(config_file)
                config = Config(config_json, name=config_file, secrets=secrets)
            except Exception:
                _error(f"Configuration JSON file cannot be loaded: {config_file}")
            return config

        if not args.config_dir:
            get_config_dir()
        config_dir = args.config_dir

        configs = []
        if not (config_dir_option_specified := isinstance(config_dir, str) and config_dir):
            config_dir = os.path.expanduser(DEFAULT_CONFIG_DIR)
        argi = 0 ; argn = len(argv)  # noqa
        while argi < argn:
            arg = argv[argi] ; argi += 1  # noqa
            arg_config = arg in ["--config", "-config", "--conf", "-conf"]
            arg_secrets = arg in ["--secrets", "-secrets", "--secret", "-secret"]
            arg_merge_config = _merges and arg in ["--merge", "-merge"]
            arg_merge_secrets = _merges and arg in ["--merge-secrets", "-merge-secrets",
                                                    "--merge-secret", "-merge-secret"]
            arg_include_config = _includes and arg in ["--includes", "-includes", "--include", "-include",
                                                       "--imports", "-imports", "--import", "-import",
                                                       "--import-config", "-import-config",
                                                       "--import-configs", "-import-configs"]
            arg_include_secrets = _includes and arg in ["--include-secrets", "-include-secrets",
                                                        "--include-secret", "-include-secret",
                                                        "--import-secrets", "-import-secrets",
                                                        "--import-secret", "-import-secret"]
            if (arg_config or arg_secrets or
                arg_merge_config or arg_merge_secrets or arg_include_config or arg_include_secrets):  # noqa
                if not config_dir_option_specified:
                    config_dir = os.getcwd()
                secrets = arg_secrets or arg_include_secrets
                argi_config = argi - 1
                if not ((argi < argn) and (config_file := argv[argi])):
                    _usage()
                configs.append(verify_config(config_file, config_dir, secrets=secrets))
                argi += 1
                while argi < argn:
                    arg = argv[argi]
                    if (arg.startswith("-") or (not (config_file := arg).endswith(".json")) or
                        (not config_file.endswith(".yaml")) or (not config_file.endswith(".yml"))):  # noqa
                        del argv[argi_config:argi] ; argi = 0 ; argn = len(argv)  # noqa
                        break
                    configs.append(verify_config(config_file, config_dir, secrets=secrets))
                    argi += 1
                if argi > 0:
                    del argv[argi_config:argi + 1]
        if _merges:
            args.configs_for_merge += configs
        elif _includes:
            args.configs_for_include = configs
        else:
            if not configs:
                configs.append(verify_config(DEFAULT_CONFIG_FILE_NAME, config_dir, secrets=False))
                configs.append(verify_config(DEFAULT_SECRETS_FILE_NAME, config_dir, secrets=True))
            args.config = configs[0]
            args.configs_for_merge = configs[1:]
            get_configs(_merges=True)
            get_configs(_includes=True)

    def get_lookup_paths() -> List[str]:
        nonlocal argv, args
        lookup_paths = []
        argi_lookup_paths = None
        argi_end_lookup_paths = len(argv)
        argi = 0 ; argn = len(argv)  # noqa
        while argi < argn:
            arg = argv[argi] ; argi += 1  # noqa
            if arg in ["--lookup", "-lookup"]:
                argi_lookup_paths = argi - 1
                continue
            elif arg.startswith("-") and argi_lookup_paths is not None:
                argi_end_lookup_paths = argi - 1
                break
            elif argi_lookup_paths is not None:
                lookup_paths.append(arg)
        if argi_lookup_paths is not None:
            del argv[argi_lookup_paths:argi_end_lookup_paths]
        args.lookup_paths = lookup_paths

    def get_password_arg():
        nonlocal argv, args
        argi = 0 ; argn = len(argv)  # noqa
        while argi < argn:
            arg = argv[argi].strip() ; argi += 1  # noqa
            if arg in ["--password", "-password", "--passwd", "-passwd"]:
                if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                    _usage()
                args.password = argv[argi]
                del argv[argi - 1:argi + 1]
                break

    def get_other_args():
        nonlocal argv, args
        argi = 0 ; argn = len(argv)  # noqa
        while argi < argn:
            arg = argv[argi].strip() ; argi += 1  # noqa
            if arg in ["--shell", "-shell", "--script", "-script", "--scripts", "-scripts",
                       "--command", "-command", "--commands", "-commands",
                       "--function", "-function", "--functions", "-functions"]:
                print(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cli.sh"))
                exit(0)
            elif arg in ["--show", "-show"]:
                args.show = True
            elif arg in ["--identity", "-identity", "--aws-secrets-name", "-aws-secrets-name"]:
                if not ((argi < argn) and (arg := argv[argi].strip())):
                    _usage()
                os.environ[ConfigWithAwsMacros._AWS_SECRET_NAME_NAME] = arg ; argi += 1  # noqa
            elif arg in ["--list", "-list"]:
                args.list = True
            elif arg in ["--tree", "-tree"]:
                args.tree = True
            elif arg in ["--dump", "-dump"]:
                args.dump = True
            elif arg in ["--raw", "-raw"]:
                args.raw = True
            elif arg in ["--verbose", "-verbose"]:
                args.verbose = True
            elif arg in ["--debug", "-debug"]:
                args.debug = True
            elif arg in ["--check", "-check"]:
                args.check = True
            elif arg in ["--nocolor", "-nocolor"]:
                args.nocolor = True
            elif arg in ["--noaws", "-noaws"]:
                args.noaws = True
            elif arg in ["--nowarnings", "-nowarnings", "--nowarning", "-nowarning"]:
                args.nowarnings = True
            elif arg in ["--warnings", "-warnings", "--warning", "-warning"]:
                args.warnings = True
            elif arg in ["--format", "-format", "--formatted", "-formatted"]:
                args.formatted = True
            elif arg in ["--password", "-password", "--passwd", "-passwd"]:
                if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                    _usage()
                pass
                args.password = argv[argi] ; argi += 1  # noqa
            elif arg in ["--version", "-version"]:
                print(get_version())
                exit(0)
            elif arg in ["--aws", "-aws", "--aws", "-aws", "--aws-profile", "-aws-profile", "--profile", "-profile"]:
                if (argi >= argn) or not (arg := argv[argi].strip()) or (not arg):
                    _usage()
                os.environ[ConfigWithAwsMacros._AWS_PROFILE_ENV_NAME] = arg ; argi += 1  # noqa
            elif arg in ["--json", "-json"]:
                args.json = True
            elif arg in ["--jsonf", "-jsonf"]:
                args.json = True
                args.formatted = True
            elif arg in ["--export", "-export", "--exports", "-exports"]:
                args.exports = True
                args.show = True
            elif arg in ["--export-file", "-export-file", "--exports-file", "-exports-file"]:
                if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                    _usage()
                args.exports_file = argv[argi] ; argi += 1  # noqa
                args.exports = True
                args.show = True
            elif arg.startswith("-"):
                _usage()
            else:
                args.lookup_paths.append(arg)
        if not args.show:
            args.noaws = True

    get_configs()
    get_lookup_paths()
    get_other_args()

    if args.lookup_paths:
        # if args.tree or args.list or args.dump or args.raw:
        if args.list or args.dump or args.raw:
            _usage()
    elif args.exports:
        _usage()
    if ((1 if args.tree else 0) + (1 if args.list else 0) + (1 if args.dump else 0)) > 1:
        _usage()
    if args.show and (args.dump or args.raw):
        _usage()
    if args.formatted:
        if args.tree or args.list or args.dump:
            _usage()
    if args.raw and (not args.dump):
        _usage()
    if args.exports:
        if args.tree or args.dump:
            _usage()
    if not (args.lookup_paths or args.tree or args.json or args.list or args.dump):
        args.tree = True
    if args.raw:
        args.show = None
    if args.json and not args.lookup_paths:
        args.formatted = True

    return args


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
    print("USAGE: hmsconfig OPTIONS [path]")
    print("OPTIONS:")
    print("--config:  list of JSON config files")
    print("--tree:    show all config data in tree format (default)")
    print("--json:    show all config data in json format")
    print("--list:    show all config data in list format")
    print("--dump:    show all config data in demp/debug format")
    print("--verbose: verbose output")
    print("--debug:   debugging output")
    sys.exit(1)


if __name__ == "__main__":
    main()
