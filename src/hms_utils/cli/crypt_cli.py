import os
import shutil
import sys
from dcicutils.command_utils import yes_or_no
from dcicutils.tmpfile_utils import temporary_file
from hms_utils.crypt_utils import decrypt_file, encrypt_file


def main():

    STDIN = "/dev/stdin"
    STDOUT = "/dev/stdout"

    def copy_file(source: str, destination: str) -> None:
        nonlocal STDOUT
        if destination == STDOUT:
            with open(source, "r") as f:
                sys.stdout.write(f.read())
        else:
            shutil.copy(source, destination)

    file = None ; encrypt = decrypt = False ; password = None ; output = None  # noqa
    yes = False ; verbose = False ; debug = False  # noqa
    argi = 0 ; argn = len(sys.argv)  # noqa
    while argi < argn:
        arg = sys.argv[argi] ; argi += 1  # noqa
        if arg in ["--encrypt", "-encrypt"]:
            encrypt = True
            if (argi < argn) and (arg := sys.argv[argi]) and (not arg.startswith("-")):
                file = arg
                argi += 1
        elif arg in ["--decrypt", "-decrypt"]:
            decrypt = True
            if (argi < argn) and (arg := sys.argv[argi]) and (not arg.startswith("-")):
                file = arg
                argi += 1
        elif arg in ["--password", "-password", "--passwd", "-passwd"]:
            if not ((argi < argn) and (password := sys.argv[argi])):
                _usage()
            argi += 1
        elif arg in ["--yes", "-yes", "--force", "-force"]:
            yes = True
        elif arg in ["--verbose", "-verbose"]:
            verbose = True
        elif arg in ["--debug", "-debug"]:
            debug = True
        elif arg in ["--output", "-output", "--out", "-out", "--to", "-to"]:
            if not ((argi < argn) and (output := sys.argv[argi])):
                _usage()
            argi += 1
        elif (arg == "-") and (not file):
            file = arg
        elif arg.startswith("-"):
            _usage()
        elif not file:
            file = arg
    if not file:
        file = STDIN
    if (file == "-") or (file == STDIN):
        file = STDIN
    if (file != STDIN) and (not os.path.isfile(file)):
        _error(f"Cannot find file: {file}")
    if not password:
        _error("Must specify a password.")
    if output:
        if (output == "-") or (output == STDOUT):
            output = STDOUT
        elif (not yes) and os.path.isfile(output):
            _error(f"Output file already exists: {output}")
        elif (output_directory := os.path.dirname(output)) and (not os.path.isdir(output_directory)):
            _error(f"Output file directory does not exist: {output_directory}")
    elif file == STDIN:
        output = STDOUT
    with temporary_file() as tmpfile:
        if encrypt:
            verb = "Encrypt"
            function = encrypt_file
        elif decrypt:
            verb = "Decrypt"
            function = decrypt_file
        else:
            _error("Must specify --encrypt or --decrypt")
        if (not output) and (not yes_or_no(f"{verb} file {file} in place?")):
            exit(0)
        if debug:
            _print(f"{verb}ing file {file} to {tmpfile}")
        elif verbose:
            _print(f"{verb}ing file in place: {file}")
        function(file, password, tmpfile)
        copy_file(tmpfile, "/tmp/foo")
        if debug:
            _print(f"Done {verb.lower()}ing file {file} to {tmpfile}")
        if output:
            file = output
        if debug:
            _print(f"Copying file {tmpfile} to: {file}")
        copy_file(tmpfile, file)
        if debug:
            _print(f"Done copying file {tmpfile} to: {file}")


def main_encrypt():
    sys.argv = ["--encrypt"] + sys.argv[1:]
    main()


def main_decrypt():
    sys.argv = ["--decrypt"] + sys.argv[1:]
    main()


def _print(message: str) -> None:
    print(message, file=sys.stderr)


def _error(message: str) -> None:
    _print(message, file=sys.stderr)
    exit(1)


def _usage():
    _error("usage: encrypt/decrypt --password password file")
    exit(1)


if __name__ == "__main__":
    sys.argv = sys.argv[1:]
    main()
