from getpass import getpass as read_password
import os
import shutil
import sys
from dcicutils.command_utils import yes_or_no
from dcicutils.tmpfile_utils import create_temporary_file_name, temporary_file
from hms_utils.crypt_utils import decrypt_file, encrypt_file
from hms_utils.argv import ARGV


def main():

    STDIN = "/dev/stdin"
    STDOUT = "/dev/stdout"

    argv = ARGV({
        ARGV.OPTIONAL(bool): ["--encrypt"],
        ARGV.OPTIONAL(bool): ["--decrypt"],
        ARGV.OPTIONAL(str): ["--output", "--out"],
        ARGV.OPTIONAL(bool): ["--yes", "--force"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--debug"],
        ARGV.OPTIONAL(str): ["--password", "--passwd"],
        ARGV.REQUIRED(str): ["file", ARGV.DEFAULT, "-"],
        ARGV.EXACTLY_ONE_OF: ["--encrypt", "--decrypt"],
    })

    def copy_file(source: str, destination: str) -> None:
        nonlocal STDOUT
        if destination == STDOUT:
            with open(source, "r") as f:
                sys.stdout.write(f.read())
        else:
            shutil.copy(source, destination)

    if argv.encrypt:
        verb = "Encrypt"
        function = encrypt_file
    elif argv.decrypt:
        verb = "Decrypt"
        function = decrypt_file

    if argv.file == "-":
        argv.file = STDIN
    if (argv.file != STDIN) and (not os.path.isfile(argv.file)):
        _error(f"Cannot find file: {argv.file}")

    if argv.output:
        if (argv.output == "-") or (argv.output == STDOUT):
            argv.output = STDOUT
        elif os.path.isfile(argv.output):
            if not (argv.yes or yes_or_no(f"Overwrite file: {argv.output} ?")):
                exit(0)
        elif (output_directory := os.path.dirname(argv.output)) and (not os.path.isdir(output_directory)):
            _error(f"Output file directory does not exist: {output_directory}")
        elif argv.file == STDIN:
            argv.output = STDOUT
    elif argv.file == STDIN:
        argv.output = STDOUT
    elif argv.yes or yes_or_no(f"{verb} file {argv.file} in place?"):
        argv.output = argv.file
    else:
        argv.output = None

    if not argv.password:
        argv.password = read_password("Enter password: ")
        if not argv.password:
            _error("Must specify a password.")
        if function == encrypt_file:
            verify_password = read_password("Verify password: ")
            if verify_password != argv.password:
                _error("Passwords to not match.")

    with temporary_file() as tmpfile:

        if argv.debug:
            _print(f"{verb}ing file {argv.file} to {tmpfile}")
        elif argv.verbose and (argv.output == argv.file):
            _print(f"{verb}ing file in place: {argv.file}")
        function(argv.file, argv.password, tmpfile)
        if argv.debug:
            _print(f"Done {verb.lower()}ing file {argv.file} to {tmpfile}")
        if argv.output:
            if argv.debug:
                _print(f"Copying file {tmpfile} to: {argv.output}")
            copy_file(tmpfile, argv.output)
            if argv.debug:
                _print(f"Done copying file {tmpfile} to: {argv.output}")
        else:
            argv.output = create_temporary_file_name()
            copy_file(tmpfile, argv.output)
            _print(f"{verb}ed file is here: {argv.output}")


def main_encrypt():
    sys.argv.insert(1, "--encrypt")
    main()


def main_decrypt():
    sys.argv.insert(1, "--decrypt")
    main()


def _print(message: str) -> None:
    print(message, file=sys.stderr)


def _error(message: str) -> None:
    print(message, file=sys.stderr)
    exit(1)


def _usage():
    _error("usage: encrypt/decrypt --password password file")
    exit(1)


if __name__ == "__main__":
    sys.argv = sys.argv
    main()
