from __future__ import annotations
import io
import json
import os
import sys
import traceback
from typing import List, Optional, Tuple
import yaml
from hms_utils.argv import ARGV, AT_LEAST_ONE_OF, AT_MOST_ONE_OF, DEPENDENCY, DEPENDS_ON, OPTIONAL, REQUIRED   # noqa
from hms_utils.chars import chars
from hms_utils.config.config import Config
from hms_utils.config.config_output import ConfigOutput
from hms_utils.config.config_with_aws_macros import ConfigWithAwsMacros
from hms_utils.crypt_utils import read_encrypted_file
from hms_utils.dictionary_parented import JSON
from hms_utils.path_utils import is_current_or_parent_relative_path
from hms_utils.type_utils import any_of_bool, at_most_one_of_bool
from hms_utils.version_utils import get_version

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
            print(f"{chars.rarrow} {config.name}"
                  f"{f' {chars.dot} decrypted' if config.decrypted else ''}")
        if args.configs_for_merge:
            for config_for_merge in args.configs_for_merge:
                print(f"{chars.rarrow_hollow} {config_for_merge.name} {chars.dot} merged"
                      f"{f' {chars.dot} decrypted' if config_for_merge.decrypted else ''}")
        if args.configs_for_include:
            for config_for_include in args.configs_for_include:
                print(f"{chars.rarrow_hollow} {config_for_include.name} {chars.dot} included"
                      f"{f' {chars.dot} decrypted' if config_for_include.decrypted else ''}")

    if not args.lookup_paths:
        if args.json:
            if args.show is True:
                data = config.lookup("/", show=args.show).sorted()
            elif args.show is False:
                data = config.data(show=False)
            else:
                data = config.data(show=None)
            print(json.dumps(data, indent=4 if args.formatted else None))
        elif args.tree or args.dump:
            ConfigOutput.print_tree(config, show=args.show, nocolor=args.nocolor, root=True, debug=args.dump)
        elif args.list:
            ConfigOutput.print_list(config, show=args.show, nocolor=args.nocolor)

    status = 0
    if args.lookup_paths:
        if args.exports:
            status = handle_exports_command(config, args)
        else:
            status = handle_lookup_command(config, args)

    if config._warnings:
        if args.warnings:
            print(f"{chars.rarrow} WARNINGS ({len(config._warnings)}):", file=sys.stderr)
            for warning in config._warnings:
                print(f"  {chars.rarrow_hollow} {warning}", file=sys.stderr)

    if args.new:
        parse_args_new()

    sys.exit(status)


def main_show_script_path():
    sys.argv = ["hmsconfig", "--functions"]
    main()


def handle_lookup_command(config: Config, args: object) -> int:
    if not args.lookup_paths:
        return 0
    status = 0 ; n = 0  # noqa
    for lookup_path in args.lookup_paths:
        if (value := config.lookup(lookup_path, show=args.show if not args.dump else None)) is None:
            status = 1
            if not args.verbose:
                continue
            value = chars.null
        if args.show and Config._contains_macro(value):
            status = 1
        if isinstance(value, JSON):
            if args.json and args.formatted:
                value = json.dumps(value.sorted(), indent=4)
            elif args.tree or args.dump:
                prefix = "...\n" if args.verbose else ("" if n == 0 else "\n")
                root = value.context_path(path_separator=config.path_separator, path_rooted=True) if args.dump else None
                value = (prefix +
                         ConfigOutput.print_tree(config, data=value.sorted(), nocolor=args.nocolor,
                                                 string=True, indent=2 if args.verbose else None,
                                                 show=args.show, root=root, debug=args.dump))
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


def parse_args_new() -> object:
    argv = ARGV({
        OPTIONAL([str]): ["--configs", "--config", "--confs", "--conf",
                          "--merge", "--merge-configs", "--merge-config", "--merge-confs", "--merge-conf"],
        OPTIONAL([str]): ["--secrets", "--secret", "--merge-secrets", "--merge-secret"],
        OPTIONAL([str]): ["--includes", "--include", "--include-configs", "--include-config",
                          "--include-confs", "--include-conf", "--imports", "--import",
                          "--import-configs", "--import-config", "import-confs", "--import-conf"],
        OPTIONAL(str): ["--config-dir", "--conf-dir", "--dir", "--directory"],
        OPTIONAL([str]): ["--lookup-paths", "--lookup-path", "--lookups", "--lookup"],
        OPTIONAL(bool): ["--tree"],
        OPTIONAL(bool): ["--list"],
        OPTIONAL(bool): ["--dump"],
        OPTIONAL(bool): ["--raw"],
        OPTIONAL(bool): ["--show"],
        OPTIONAL(str): ["--identity"],
        OPTIONAL(str): ["--password"],
        OPTIONAL(bool): ["--json"],
        OPTIONAL(bool): ["--format", "--formatted"],
        OPTIONAL(bool): ["--exports", "--export"],
        OPTIONAL(bool): ["--functions", "--function", "--shell"],
        OPTIONAL(str): ["--exports-file", "--export-file"],
        OPTIONAL(bool): ["--noaws"],
        OPTIONAL(str): ["--aws-profile", "--aws", "--profile", "--env"],
        OPTIONAL(bool): ["--nocolor"],
        OPTIONAL(bool): ["--warnings", "--warning"],
        OPTIONAL(bool): ["--verbose"],
        OPTIONAL(bool): ["--debug"],
        OPTIONAL(bool): ["--version"],
        OPTIONAL(bool): ["--new"],
        AT_MOST_ONE_OF: ["--tree", "--list", "--json", "--dump", "--exports", "--functions"],
        DEPENDENCY: ["--format", DEPENDS_ON, "--json"]
    }, parse=True, exit=False)

    argv.parse(exit=False)
    print(">>> NEW ARGV PARSING:")
    print(json.dumps(argv._dict, indent=4))


def parse_args(argv: List[str]) -> object:

    # TODO: Use to ARGV class ...

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
        show = None
        profile = None
        noaws = False
        nocolor = False
        formatted = False
        verbose = False
        password = False
        warnings = False
        debug = False
        new = False

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

        def read_file(file: str) -> Tuple[Optional[dict], bool]:
            if args.password:
                try:
                    if data := read_encrypted_file(file, password=args.password):
                        if file.endswith(".yaml") or config_file.endswith(".yml"):
                            return yaml.safe_load(data), True
                        else:
                            return json.loads(data), True
                except Exception:
                    pass
            with io.open(file, "r") as f:
                if file.endswith(".yaml") or file.endswith(".yml"):
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            return data, False

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
                config_json, decrypted = read_file(config_file)
                config = Config(config_json, name=config_file, secrets=secrets, decrypted=decrypted)
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
                if not is_current_or_parent_relative_path(config_file):
                    config_file = os.path.join(".", config_file)
                configs.append(verify_config(config_file, config_dir, secrets=secrets))
                argi += 1
                while argi < argn:
                    arg = argv[argi]
                    if (arg.startswith("-") or (not ((config_file := arg).endswith(".json") or
                                                     config_file.endswith(".yaml") or config_file.endswith(".yml")))):  # noqa
                        del argv[argi_config:argi] ; argi = 0 ; argn = len(argv)  # noqa
                        break
                    if not is_current_or_parent_relative_path(config_file):
                        config_file = os.path.join(".", config_file)
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
                print(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_cli.sh"))
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
            elif arg in ["--warnings", "-warnings", "--warning", "-warning"]:
                args.warnings = True
            elif arg in ["--format", "-format", "--formatted", "-formatted"]:
                args.formatted = True
            elif arg in ["--new"]:
                args.new = True
            elif arg in ["--password", "-password", "--passwd", "-passwd"]:
                if (argi >= argn) or not (arg := argv[argi]) or (not arg):
                    _usage()
                pass
                args.password = argv[argi] ; argi += 1  # noqa
            elif arg in ["--version", "-version"]:
                print(get_version())
                exit(0)
            elif arg in ["--aws", "-aws", "--aws", "-aws",
                         "--aws-profile", "-aws-profile", "--profile", "-profile", "--env", "-env"]:
                if (argi >= argn) or not (arg := argv[argi].strip()) or (not arg):
                    _usage()
                args.profile = arg ; argi += 1  # noqa
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

    get_configs()
    get_lookup_paths()
    get_other_args()

    if args.lookup_paths:
        if any_of_bool(args.list):
            _usage()
    else:
        if args.exports:
            _usage()
        if not at_most_one_of_bool(args.json, args.tree, args.list, args.dump):
            _usage()
    if not at_most_one_of_bool(args.tree, args.list, args.json, args.dump):
        _usage()
    if args.formatted:
        if args.tree or args.list or args.dump:
            _usage()
    if args.exports:
        if args.tree or args.dump:
            _usage()
    if not (args.lookup_paths or args.tree or args.json or args.list or args.dump):
        args.tree = True
    if args.raw:
        if args.show is not None:
            _usage()
        args.show = None
    elif args.show is None:
        args.show = False
    if args.show is False:
        args.noaws = True

    if args.profile:
        os.environ[ConfigWithAwsMacros._AWS_PROFILE_ENV_NAME] = args.profile
        if not args.config._aws_current_account_number(args.profile):
            _error(f"Specified AWS profile does not work: {args.profile}")

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
