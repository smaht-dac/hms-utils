from __future__ import annotations
import io
import json
import os
import sys
import traceback
from typing import List, Optional
from hms_utils.chars import chars
from hms_utils.config.config import Config
from hms_utils.config.config_output import ConfigOutput
from hms_utils.path_utils import is_current_or_parent_relative_path

DEFAULT_CONFIG_DIR = "~/.config/hms"
DEFAULT_CONFIG_FILE_NAME = "config.json"
DEFAULT_SECRETS_FILE_NAME = "secrets.json"
DEFAULT_PATH_SEPARATOR = "/"
DEFAULT_EXPORT_NAME_SEPARATOR = ":"
AWS_PROFILE_ENV_NAME = "AWS_PROFILE"
OBFUSCATED_VALUE = "********"

SUPPRESS_AWS_SECRET_NOT_FOUND_WARNING = False  # Hack


def main(argv: Optional[List] = None):
    parse_args(argv if isinstance(argv, list) else sys.argv[1:])
    sys.exit(0)


def main_show_script_path():
    sys.argv = ["hms-config", "--functions"]
    main()


def parse_args(argv: List[str]) -> object:

    class Args:
        config_dir = None
        config = None
        configs_for_merge = []
        configs_for_import = []
        lookup_paths = []
        list = False
        files = False
        dump = False
        raw = False
        show = False
        noaws = False
        identity = None
        verbose = False
        debug = False

    args = Args()

    def get_configs(_merges: bool = False, _imports: bool = False) -> None:

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

        def get_config_dir() -> None:
            nonlocal argv, args
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
                with io.open(config_file) as f:
                    config_json = json.load(f)
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
        argi = 0
        while argi < len(argv):
            arg = argv[argi] ; argi += 1  # noqa
            arg_config = arg in ["--config", "-config", "--conf", "-conf"]
            arg_secrets = arg in ["--secrets", "-secrets", "--secret", "-secret"]
            arg_merge_config = _merges and arg in ["--merge", "-merge"]
            arg_merge_secrets = _merges and arg in ["--merge-secrets", "-merge-secrets",
                                                    "--merge-secret", "-merge-secret"]
            arg_import_config = _imports and arg in ["--imports", "-imports", "--import", "-import"]
            arg_import_secrets = _imports and arg in ["--import-secrets", "-import-secrets",
                                                      "--import-secret", "-import-secret"]
            if (arg_config or arg_secrets or
                arg_merge_config or arg_merge_secrets or arg_import_config or arg_import_secrets):  # noqa
                if not config_dir_option_specified:
                    config_dir = os.getcwd()
                secrets = arg_secrets or arg_import_secrets
                argi_config = argi - 1
                if not ((argi < len(argv)) and (config_file := argv[argi])):
                    _usage()
                configs.append(verify_config(config_file, config_dir, secrets=secrets))
                argi += 1
                while argi < len(argv):
                    arg = argv[argi]
                    if arg.startswith("-") or not (config_file := arg).endswith(".json"):
                        del argv[argi_config:argi] ; argi = 0  # noqa
                        break
                    configs.append(verify_config(config_file, config_dir, secrets=secrets))
                    argi += 1
                if argi > 0:
                    del argv[argi_config:argi + 1]
        if _merges:
            args.configs_for_merge += configs
        elif _imports:
            args.configs_for_import = configs
        else:
            if not configs:
                configs.append(verify_config(DEFAULT_CONFIG_FILE_NAME, config_dir, secrets=False))
                configs.append(verify_config(DEFAULT_SECRETS_FILE_NAME, config_dir, secrets=True))
            args.config = configs[0]
            args.configs_for_merge = configs[1:]
            get_configs(_merges=True)
            get_configs(_imports=True)

    def get_lookup_paths() -> List[str]:
        nonlocal argv, args
        lookup_paths = []
        argi_lookup_paths = None
        argi_end_lookup_paths = len(argv)
        argi = 0
        while argi < len(argv):
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

    def get_other_args():
        nonlocal argv, args
        argi = 0
        while argi < len(argv):
            arg = argv[argi].strip() ; argi += 1  # noqa
            if arg in ["--show", "-show"]:
                args.show = True
            elif arg in ["--noaws", "-noaws"]:
                args.noaws = True
            elif arg in ["--identity", "-identity", "--aws-secrets-name", "-aws-secrets-name"]:
                if not ((argi < len(argv)) and (identity := argv[argi].strip())):
                    _usage()
                args.identity = identity
            elif arg in ["--list", "-list"]:
                args.list = True
            elif arg in ["--files", "-files"]:
                args.files = True
            elif arg in ["--dump", "-dump", "--tree", "-tree"]:
                args.dump = True
            elif arg in ["--raw", "-raw"]:
                args.raw = True
            elif arg in ["--verbose", "-verbose"]:
                args.verbose = True
            elif arg in ["--debug", "-debug"]:
                args.debug = True
            elif arg.startswith("-"):
                _usage()
            else:
                args.lookup_paths.append(arg)

    get_lookup_paths()
    get_configs()
    get_other_args()
    merged_paths, unmerged_paths = args.config.merge(args.configs_for_merge)
    args.config.imports(args.configs_for_import)
    config = args.config

    #   print(f"config_dir: [{config_dir}]")
    #   print(f"configs: {configs}")
    #   for config in configs:
    #       print(f"configs.name: {config.name}")
    #       print(f"configs.secrets: {config.secrets}")
    #   print(argv)

    # config = configs[0]
    # configs_for_merge = configs[1:]
    # merged_paths, unmerged_paths = config.merge(configs_for_merge)
    # config.imports(imports)

    if args.identity:
        args.config.aws_secrets_name = args.identity

    if args.dump or args.list or args.debug or args.files:
        if args.files:
            print(f"Default config directory: {args.config_dir}")
        if config.name:
            print(f"Main config file: {config.name}")
        if args.configs_for_merge:
            for config_for_merge in args.configs_for_merge:
                if config_for_merge.name:
                    print(f"Merged config file: {config_for_merge.name}")
        if args.configs_for_import:
            for config_for_import in args.configs_for_import:
                if config_for_import.name:
                    print(f"Imported config file: {config_for_import.name}")

    if args.dump:
        ConfigOutput.print_tree(config, show=args.show, raw=args.raw)

    if args.list:
        ConfigOutput.print_list(config, show=args.show)

    if args.debug:
        config._dump_for_testing(check=args.verbose)

    if args.lookup_paths:
        status = 0
        for lookup_path in args.lookup_paths:
            if (value := config.lookup(lookup_path, show=args.show)) is None:
                value = chars.null
                status = 1
            if args.verbose:
                print(f"{lookup_path}: {value}")
            else:
                print(f"{value}")
        exit(status)

    # import pdb ; pdb.set_trace()  # noqa
    # xxx = config.lookup('identity/xyzzy')
    # print(xxx)
    pass


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
#   testargv = [
#       "--config",
#       "~/.config/hms/secrets.json",
#       "~/.config/hms/config.json",
#       "--show",
#       "--verbose",
#       "--lookup",
#       "/auth0/client",
#       "/identity/smaht/foursight/wolf",
#       "--debug",
#       "--dump",
#       "asdfa",
#       "--identity",
#       "C4AppConfigFoursightSmahtDevelopment"
#   ]
#   main(testargv)
