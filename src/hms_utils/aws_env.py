from __future__ import annotations
from boto3 import Session as BotoSession
from collections import namedtuple
import configparser
from datetime import datetime, timedelta
import io
import os
import re
import subprocess
import sys
from typing import List, Optional, Tuple
from hms_utils.terminal_utils import terminal_color
from hms_utils.threading_utils import run_concurrently
from hms_utils.version_utils import get_version

# ----------------------------------------------------------------------------------------------------------------------
# Convenience utility to view/manage SSO/Okta-based AWS credentials, defined in the ~/.aws/config file.
# Mostly just viewing features; the only "manage" feature being setting the default profile;
# and also refreshing credentials (i.e. logging in via aws sso login). Usage:
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# usage: python aws_env.py [profile-name-pattern] [nocheck]
#        python aws_env.py default [profile-name] | aws_env nodefault
#        python aws_env.py current [profile-name] | aws_env nocurrent
#        python aws_env.py refresh [profile-name]
# ----------------------------------------------------------------------------------------------------------------------

AWS_CONFIG_FILE_PATH = os.path.expanduser("~/.aws/config")
AWS_PROFILE_ENVIRONMENT_VARIABLE_NAME = "AWS_PROFILE"
AWS_COMMAND_PATH = "/usr/local/bin/aws"
AWS_DEFAULT_SECTION_NAME = "default"


class AwsProfiles(List[object]):

    def __init__(self, _default: Optional[object] = None, _current: Optional[object] = None) -> None:
        self.default = _default
        self.current = _current
        pass

    def filter(self, aws_profile_name_pattern: str) -> AwsProfiles:
        aws_profiles_filtered = AwsProfiles(self.default)
        if isinstance(aws_profile_name_pattern, str) and aws_profile_name_pattern:
            aws_profile_name_pattern = aws_profile_name_pattern.lower()
            for aws_profile in self:
                if aws_profile_name_pattern in aws_profile.name.lower():
                    aws_profiles_filtered.append(aws_profile)
        return aws_profiles_filtered

    def find(self, aws_profile_name: str) -> Optional[object]:
        if isinstance(aws_profile_name, str) and aws_profile_name:
            aws_profile_name = aws_profile_name.lower()
            for aws_profile in self:
                if aws_profile.name.lower() == aws_profile_name:
                    return aws_profile
        return None

    @staticmethod
    def read() -> AwsProfiles:

        global AWS_CONFIG_FILE_PATH, AWS_DEFAULT_SECTION_NAME

        def create_aws_profile(name: str, account_number: str, default: bool = False, current: bool = False):
            return namedtuple("aws_profile", ["name", "account", "default", "current"])(
                    name, account_number, default is True, name == get_current_aws_profile_name())

        aws_config = configparser.ConfigParser()
        aws_config.read(AWS_CONFIG_FILE_PATH)
        aws_profiles = AwsProfiles()
        aws_default_profile = None

        if aws_default_section_name := aws_config_section_name(aws_config, AWS_DEFAULT_SECTION_NAME):
            if aws_default_profile_account_number := aws_config.get(aws_default_section_name, "sso_account_id"):
                aws_default_profile_name = (aws_config.get(aws_default_section_name, "sso_session") or
                                            AWS_DEFAULT_SECTION_NAME)
                aws_default_profile = create_aws_profile(aws_default_profile_name,
                                                         aws_default_profile_account_number, default=True)
                aws_profiles.default = aws_default_profile

        ndefaults = 0
        for aws_section_name in aws_config.sections():
            aws_section_name = normalize_string(aws_section_name)
            if not aws_section_name.startswith("profile "):
                continue
            aws_profile_name = aws_section_name[len("profile "):].strip()
            aws_account_number = aws_config.get(aws_section_name, "sso_account_id", fallback=None)
            aws_default = (aws_account_number == aws_default_profile.account) if aws_default_profile else False
            if aws_default:
                ndefaults += 1
            aws_profile = create_aws_profile(aws_profile_name, aws_account_number, default=aws_default)
            aws_profiles.append(aws_profile)
            if aws_profile.current:
                aws_profiles.current = aws_profile

        if ndefaults > 1:
            print(f"WARNING: AWS default section refers to more than one account number: {aws_default_profile.account}")
        elif (ndefaults == 0) and aws_default_profile:
            print(f"WARNING: AWS default section references non-existent account number: {aws_default_profile.account}")

        return aws_profiles._sorted()

    def _sorted(self) -> AwsProfiles:
        aws_profiles_sorted = AwsProfiles(_default=self.default, _current=self.current)
        for aws_profile in sorted(self, key=lambda item: item.name):
            aws_profiles_sorted.append(aws_profile)
        return aws_profiles_sorted


class CHAR:
    check = "✓"
    xmark = "✗"
    rarrow = "▶"
    rarrow_hollow = "▷"
    larrow = "◀"
    bullet = "•"
    bullet_hollow = "◦"


def verify_aws_account(aws_profile: object) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    aws_profile_name = aws_profile.name
    try:
        boto_session = BotoSession(profile_name=aws_profile_name)
        access_key_id = None
        expiration_time = None
        valid_duration = None
        try:
            credentials = boto_session.get_credentials()
            access_key_id = credentials.access_key
            try:
                # The credentials._expiry_time moves forward in time
                # as it is used; this is expected (I'm pretty sure).
                expiration_time = credentials._expiry_time.astimezone()
                valid_duration = get_duration(expiration_time - datetime.now(tz=expiration_time.tzinfo))
                expiration_time = expiration_time.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        except Exception:
            pass
        boto_sts = boto_session.client("sts")
        account_number = boto_sts.get_caller_identity()["Account"]
        if isinstance(account_number, str) and (len(account_number) > 0):
            return True, access_key_id, expiration_time, valid_duration
    except Exception:
        pass
    return False, None, None, None


def get_current_aws_profile_name() -> Optional[str]:
    global AWS_PROFILE_ENVIRONMENT_VARIABLE_NAME
    return os.environ.get(AWS_PROFILE_ENVIRONMENT_VARIABLE_NAME, None)


def perform_login(aws_profile_name: str, verbose: bool = False) -> None:
    global AWS_COMMAND_PATH
    command = [AWS_COMMAND_PATH, "sso", "login", "--profile", aws_profile_name]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        look_for_code = False
        while True:
            if (not (output := process.stdout.readline())) and (process.poll() is not None):
                break
            if (look_for_code is not None) and (output := output.strip()):
                if "enter the code" in output.lower():
                    look_for_code = True
                elif look_for_code:
                    print(f"Confirm this code in your browser to login to {aws_profile_name}: {output.strip()} ... ",
                          end="", flush=True)
                    look_for_code = None
        if stderr_output := process.stderr.read().strip():
            print(f"\nNot confirmed or login failed: {aws_profile_name}")
            if verbose is True:
                print(f"\nError output on login ({aws_profile_name}):")
                print(stderr_output)
        else:
            print("OK")
        process.wait()
    except Exception as e:
        print(f"\nNot confirmed or login failed: {aws_profile_name}")
        if verbose is True:
            print(f"EXCEPTION: {str(e)}")


def print_aws_profile_line(aws_profile: object, verified_result: Optional[tuple] = None, nocheck: bool = False,
                           current: Optional[str] = None, login: bool = False, verbose: bool = False) -> bool:
    global AWS_DEFAULT_SECTION_NAME
    verified = False if not verified_result else verified_result[0]
    if login:
        perform_login(aws_profile.name, verbose=verbose)
    aws_profile_name_current = get_current_aws_profile_name()
    if current and not aws_profile.current:
        return False
    if ((aws_profile_name_current == aws_profile.name) or aws_profile.default or
        (aws_profile.name == AWS_DEFAULT_SECTION_NAME)):  # noqa
        line = f"{CHAR.rarrow} {aws_profile.name}: "
    else:
        line = f"{CHAR.rarrow_hollow} {aws_profile.name}: "
    if aws_profile.account:
        line += f"{aws_profile.account}"
    else:
        line += "<no account number>"
    if not nocheck:
        if verified_result:
            verified, access_key_id, expiration_time, valid_duration = verified_result
        else:
            verified, access_key_id, expiration_time, valid_duration = verify_aws_account(aws_profile)
        if verified:
            line += f" {CHAR.check}"
            if access_key_id and verbose:
                line += f" {access_key_id}"
            if expiration_time and verbose:
                if verbose:
                    line += f" {CHAR.rarrow_hollow} {expiration_time}"
                else:
                    line += f" {expiration_time}"
            if valid_duration and verbose:
                line += f" {CHAR.bullet_hollow} {valid_duration}"
        else:
            line += f" {CHAR.xmark}"
    if aws_profile.default:
        line += f" {CHAR.larrow} default"
    if aws_profile_name_current == aws_profile.name:
        AwsProfiles().read().default
        if ((not aws_profile.default) and
            (aws_default_profile := AwsProfiles().read().default) and
            (aws_default_profile.name != aws_profile.name)):  # noqa
            # If both current and default set and current is not the same as default then
            # make the current one stand out, as this is the one that will be used over default.
            line += f" {CHAR.larrow} {terminal_color('current', 'red', bold=True, underline=True)}"
        else:
            line += f" {CHAR.larrow} current"
    print(line)
    return verified


def set_default_profile(aws_profile: object, auto_confirm: bool = False) -> bool:
    global AWS_CONFIG_FILE_PATH, AWS_DEFAULT_SECTION_NAME
    aws_profile_name = aws_profile.name
    aws_config = configparser.ConfigParser()
    aws_config.read(AWS_CONFIG_FILE_PATH)
    if aws_config_section_name(aws_config, AWS_DEFAULT_SECTION_NAME):
        if aws_config.get(AWS_DEFAULT_SECTION_NAME, "sso_account_id", fallback=None) == aws_profile.account:
            print(f"AWS profile is already the default: {aws_profile.name}")
            return False
    if aws_profile_section_name := aws_config_section_name(aws_config, f"profile {aws_profile_name}"):
        if aws_default_section_name := aws_config_section_name(aws_config, AWS_DEFAULT_SECTION_NAME):
            aws_config.remove_section(aws_default_section_name)
        aws_config.add_section(AWS_DEFAULT_SECTION_NAME)
        for name, value in aws_config.items(aws_profile_section_name):
            aws_config.set(AWS_DEFAULT_SECTION_NAME, name, value)
        if aws_session_section_name := aws_config_section_name(aws_config, f"sso-session {aws_profile_name}"):
            if (aws_default_session_section_name :=
                aws_config_section_name(aws_config, f"sso-session {AWS_DEFAULT_SECTION_NAME}")):  # noqa
                aws_config.remove_section(aws_default_session_section_name)
            aws_config.add_section(f"sso-session {AWS_DEFAULT_SECTION_NAME}")
            for name, value in aws_config.items(aws_session_section_name):
                aws_config.set(f"sso-session {AWS_DEFAULT_SECTION_NAME}", name, value)
    if auto_confirm is not True:
        if not confirm(f"Update AWS config file with new default ({aws_profile_name}): {AWS_CONFIG_FILE_PATH} "):
            return False
    with open(AWS_CONFIG_FILE_PATH, "w") as f:
        aws_config.write(f)
    return True


def remove_default_profile(default: Optional[object] = None, auto_confirm: bool = False) -> None:
    global AWS_CONFIG_FILE_PATH
    aws_config = configparser.ConfigParser()
    aws_config.read(AWS_CONFIG_FILE_PATH)
    if not (aws_default_section_name := aws_config_section_name(aws_config, AWS_DEFAULT_SECTION_NAME)):
        print("No default AWS profile to remove.")
        return
    if aws_default_section_name := aws_config_section_name(aws_config, AWS_DEFAULT_SECTION_NAME):
        if auto_confirm is not True:
            if not confirm(f"Update AWS config file to remove default"
                           f" profile ({default.name}): {AWS_CONFIG_FILE_PATH} "):
                return
        aws_config.remove_section(aws_default_section_name)
        if aws_session_section_name := aws_config_section_name(aws_config, f"sso-session {AWS_DEFAULT_SECTION_NAME}"):
            aws_config.remove_section(aws_session_section_name)
        with open(AWS_CONFIG_FILE_PATH, "w") as f:
            aws_config.write(f)


def aws_config_section_name(aws_config: configparser.ConfigParser, aws_section_name: str) -> Optional[str]:
    # Use this rather than aws_config.has_section to handle weird spacing in ~/.aws/config;
    # returns the actual section name as it is in ~/.aws/config or None if not found.
    if (isinstance(aws_config, configparser.ConfigParser) and
        isinstance(aws_section_name := normalize_string(aws_section_name).lower(), str)):  # noqa
        for aws_config_section_name in aws_config.sections():
            if normalize_string(aws_config_section_name).lower() == aws_section_name:
                return aws_config_section_name
    return None


def get_duration(value: timedelta) -> str:
    total_seconds = int(value.total_seconds())
    hours, hours_remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(hours_remainder, 60)
    return f"{hours}:{minutes:02}:{seconds:02}"


def normalize_string(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip() if isinstance(value, str) else ""


def confirm(message: str) -> bool:
    return input(f"{message}? ").lower() in ["y", "yes"]


def usage(status: int = 1) -> None:
    print("usage: python aws_env.py [profile-name-pattern] [nocheck]")
    print("       python aws_env.py login [profile-name]")
    print("       python aws_env.py default [profile-name]")
    print("       python aws_env.py nodefault")
    print("       python aws_env.py current [profile-name]")
    print("       python aws_env.py nocurrent")
    sys.exit(status)


def main() -> None:

    global AWS_CONFIG_FILE_PATH, AWS_PROFILE_ENVIRONMENT_VARIABLE_NAME

    nocheck = False
    default = False
    nodefault = False
    current = False
    nocurrent = False
    noasync = False
    login = False
    yes = False
    profile_name_pattern = None
    verbose = False
    current_export_file = None
    post_current_export_file = False

    if os.environ.get("AWS_CONFIG"):
        AWS_CONFIG_FILE_PATH = os.environ.get("AWS_CONFIG")

    argi = 0
    args = []
    while argi < len(argv := sys.argv[1:]):
        arg = argv[argi]
        if (arg == "--config") or (arg == "-config") or (arg == "--conf") or (arg == "-conf"):
            argi += 1
            if argi >= len(argv):
                usage()
            AWS_CONFIG_FILE_PATH = argv[argi]
        else:
            args.append(arg)
        argi += 1

    if not os.path.exists(AWS_CONFIG_FILE_PATH):
        print(f"AWS config file not found: {AWS_CONFIG_FILE_PATH}")
        sys.exit(2)
    if not (aws_profiles := AwsProfiles.read()):
        print(f"AWS config file contains NO profiles: {AWS_CONFIG_FILE_PATH}")
        sys.exit(3)

    # Since this is a convenience script, for convenience allow
    # a multitude of option variations so we don't need to remember.
    argi = 0
    while argi < len(args):
        arg = args[argi]
        if (arg == "--shell") or (arg == "-shell"):
            print(os.path.join(os.path.dirname(os.path.abspath(__file__)), "aws_env.sh"))
            exit(1)
        elif ((arg == "--nocheck") or (arg == "-nocheck") or (arg == "nocheck") or
              (arg == "--nc") or (arg == "-nc") or (arg == "nc") or (arg == "--n") or (arg == "-n") or
              (arg == "--quick") or (arg == "-quick") or (arg == "quick") or (arg == "--q") or (arg == "-q")):  # noqa
            nocheck = True
        elif ((arg == "--active") or (arg == "-active") or (arg == "active") or
              (arg == "--activate") or (arg == "-activate") or (arg == "activate") or
              (arg == "--current") or (arg == "-current") or (arg == "current") or (arg == "--c") or (arg == "-c")):
            current = True
        elif ((arg == "--noactive") or (arg == "-noactive") or (arg == "active") or
              (arg == "--deactive") or (arg == "-deactive") or (arg == "deactive") or
              (arg == "--deactivate") or (arg == "-deactivate") or (arg == "deactivate") or
              (arg == "--nocurrent") or (arg == "-nocurrent") or (arg == "nocurrent")):
            nocurrent = True
        elif ((arg == "--refresh") or (arg == "-refresh") or (arg == "refresh") or (arg == "--r") or (arg == "-r") or
              (arg == "--login") or (arg == "-login") or (arg == "login")):
            login = True
        elif (arg == "--default") or (arg == "-default") or (arg == "default") or (arg == "--d") or (arg == "-d"):
            default = True
        elif (arg == "--nodefault") or (arg == "-nodefault") or (arg == "nodefault"):
            nodefault = True
        elif arg in ["--noasync", "-noasync", "noasync"]:
            noasync = True
        elif (arg == "--yes") or (arg == "-yes") or (arg == "yes") or (arg == "--y") or (arg == "-y"):
            yes = True
        elif (arg == "--verbose") or (arg == "-verbose") or (arg == "verbose") or (arg == "--v") or (arg == "-v"):
            verbose = True
        elif (arg == "--help") or (arg == "-help") or (arg == "help") or (arg == "--h") or (arg == "-h"):
            usage(0)
        elif (arg == "--current-export-file"):  # to support aws_env.sh script
            if (argi := argi + 1) >= len(args):
                usage(1)
            current_export_file = args[argi]
        elif (arg == "--post-current-export-file"):  # to support aws_env.sh script
            post_current_export_file = args[argi]
        elif arg in ["--version", "-version"]:
            print(f"hms-utils version: {get_version()}")
            exit(0)
        elif arg.startswith("-"):
            usage(1)
        elif profile_name_pattern:
            usage(1)
        else:
            profile_name_pattern = arg
        argi += 1

    if default:
        if nodefault or current or nocurrent:
            usage()
    if nodefault:
        if default or current or nocurrent or login:
            usage()
    if current:
        if default or nodefault or nocurrent:
            usage()
    if nocurrent:
        if current or default or nodefault or login:
            usage()

    if profile_name_pattern:
        if nodefault:
            print("With the --nodefault option (to remove the default AWS profile) do not specify an AWS profile name.")
            sys.exit(5)
        elif nocurrent:
            if not aws_profiles.current:
                print("With the --nocurrent option (to deactivate the"
                      f" current AWS profile) do not specify an AWS profile name.")
            sys.exit(5)
        elif not (aws_profiles_selected := aws_profiles.filter(profile_name_pattern)):
            print(f"AWS profile name ({profile_name_pattern})"
                  f" does not match any profiles in AWS config: {AWS_CONFIG_FILE_PATH}")
            for aws_profile in aws_profiles:
                print_aws_profile_line(aws_profile, nocheck=True)
            sys.exit(6)
        elif default:
            if len(aws_profiles_selected) != 1:
                print(f"The --default option requires a SINGLE existing AWS profile name (multiple matches: "
                      f"{', '.join([item.name for item in aws_profiles_selected])}).")
                sys.exit(7)
            if aws_profiles_selected[0].name != profile_name_pattern:
                print(f"The --default option requires an EXACT matching"
                      f" AWS profile name ({aws_profiles_selected[0].name}).")
                sys.exit(8)
        elif current:
            if len(aws_profiles_selected) != 1:
                print(f"The --current option requires a SINGLE existing AWS profile name (multiple matches: "
                      f"{', '.join([item.name for item in aws_profiles_selected])}).")
                sys.exit(9)
            if aws_profiles_selected[0].name != profile_name_pattern:
                print(f"The --current option requires an EXACT matching"
                      f" AWS profile name ({aws_profiles_selected[0].name}).")
                sys.exit(10)
    elif default:
        if not aws_profiles.default:
            print("No AWS profile is currently the default.")
            print("Use the --default option to set the default profile to an existing AWS profile name.")
            sys.exit(11)
        verified = print_aws_profile_line(aws_profiles.default, nocheck=nocheck, login=login, verbose=verbose)
        sys.exit(0 if verified or nocheck else 1)
    elif current:
        if not aws_profiles.current:
            print("No AWS profile is currently active.")
            print("Use the --current option to set the active profile to an existing AWS profile name.")
            sys.exit(12)
        verified = print_aws_profile_line(aws_profiles.current, nocheck=nocheck, login=login, verbose=verbose)
        sys.exit(0 if verified or nocheck else 1)
    else:
        aws_profiles_selected = aws_profiles

    if default:
        aws_profile_default = aws_profiles_selected[0]
        if set_default_profile(aws_profile_default, auto_confirm=yes):
            aws_profile_default = AwsProfiles.read().find(aws_profile_default.name)
        verified = print_aws_profile_line(aws_profile_default,
                                          nocheck=nocheck, current=current, login=login, verbose=verbose)
        sys.exit(0 if verified or nocheck else 1)
    elif nodefault:
        remove_default_profile(default=aws_profiles.default, auto_confirm=yes)
        sys.exit(0)
    elif nocurrent:
        if not aws_profiles.current:
            if not post_current_export_file:
                print("No current AWS profile to deactivate.")
            exit(0)
        if current_export_file and not os.path.exists(current_export_file):
            with io.open(current_export_file, "w") as f:
                f.write(f"unset {AWS_PROFILE_ENVIRONMENT_VARIABLE_NAME}")
        else:
            print(f"To deactivate the current AWS profile ({aws_profiles.current.name}) execute:"
                  f" unset {AWS_PROFILE_ENVIRONMENT_VARIABLE_NAME}")
        sys.exit(0)
    elif current:
        if (aws_profile_current := aws_profiles_selected[0]).current:
            if not post_current_export_file:
                print(f"This AWS profile is already currently active: {aws_profile_current.name}")
            verified = print_aws_profile_line(aws_profile_current, nocheck=nocheck, login=login, verbose=verbose)
            sys.exit(0 if verified or nocheck else 1)
        else:
            if current_export_file and not os.path.exists(current_export_file):
                with io.open(current_export_file, "w") as f:
                    f.write(f"export {AWS_PROFILE_ENVIRONMENT_VARIABLE_NAME}={aws_profile_current.name}")
            else:
                print(f"To make this AWS profile ({arg}) current execute:"
                      f" export {AWS_PROFILE_ENVIRONMENT_VARIABLE_NAME}={aws_profile_current.name}")
            sys.exit(0)

    if (len(aws_profiles_selected) > 1) or verbose:
        print("AWS profiles", end="")
        if profile_name_pattern:
            print(" matching '", end="")
            print(profile_name_pattern, end="")
            print("'", end="")
        print(f" in config: {AWS_CONFIG_FILE_PATH}")
    if (noasync is not True) and (len(aws_profiles_selected) > 1):
        aws_profile_results = {}
        def function(aws_profile: object):  # noqa
            nonlocal aws_profile_results
            aws_profile_results[aws_profile] = verify_aws_account(aws_profile)
        run_concurrently([lambda item=item: function(item) for item in aws_profiles_selected], nthreads=12)
        for aws_profile in sorted(aws_profile_results, key=lambda item: item.name):
            print_aws_profile_line(aws_profile, nocheck=nocheck, current=current, login=login, verbose=verbose,
                                   verified_result=aws_profile_results[aws_profile])
    else:
        for aws_profile in aws_profiles_selected:
            verified = print_aws_profile_line(aws_profile, nocheck=nocheck,
                                              current=current, login=login, verbose=verbose)
            if len(aws_profiles_selected) == 1:
                # If only a single profile selected then make the exit status correspond to its verified state.
                sys.exit(0 if verified or nocheck else 1)

    sys.exit(0)


if __name__ == "__main__":
    main()
