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
        ARGV.OPTIONAL(str): ["--encrypt"],
        ARGV.OPTIONAL(str): ["--decrypt"],
        ARGV.OPTIONAL(str): ["--output", "--out"],
        ARGV.OPTIONAL(bool): ["--yes", "--force"],
        ARGV.OPTIONAL(bool): ["--verbose"],
        ARGV.OPTIONAL(bool): ["--debug"],
        ARGV.OPTIONAL(str): ["--password", "--passwd"],
        ARGV.OPTIONAL(str): ["file"],
        ARGV.ONE_OF: ["--encrypt", "--decrypt", "file"]
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
        file = argv.encrypt
        function = encrypt_file
    elif argv.decrypt:
        verb = "Decrypt"
        file = argv.decrypt
        function = decrypt_file
    else:
        _error("Must specify --encrypt or --decrypt")

    if file == "-":
        file = STDIN
    if (file != STDIN) and (not os.path.isfile(file)):
        _error(f"Cannot find file: {file}")

    if argv.output:
        if (argv.output == "-") or (argv.output == STDOUT):
            argv.output = STDOUT
        elif (not argv.yes) and os.path.isfile(argv.output):
            _error(f"Output file already exists: {argv.output}")
        elif (output_directory := os.path.dirname(argv.output)) and (not os.path.isdir(output_directory)):
            _error(f"Output file directory does not exist: {output_directory}")
        elif file == STDIN:
            argv.output = STDOUT
    elif file == STDIN:
        argv.output = STDOUT
    elif argv.yes or yes_or_no(f"{verb} file {file} in place?"):
        argv.output = file
    else:
        argv.output = None

    if not argv.password:
        argv.password = read_password("Enter password: ")
        if not argv.password:
            _error("Must specify a password.")

    with temporary_file() as tmpfile:

        if argv.debug:
            _print(f"{verb}ing file {file} to {tmpfile}")
        elif argv.verbose and (argv.output == file):
            _print(f"{verb}ing file in place: {file}")
        function(file, argv.password, tmpfile)
        if argv.debug:
            _print(f"Done {verb.lower()}ing file {file} to {tmpfile}")
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
