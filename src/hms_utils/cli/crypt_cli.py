import os
import shutil
import sys
from dcicutils.command_utils import yes_or_no
from dcicutils.tmpfile_utils import temporary_file
from hms_utils.crypt_utils import decrypt_file, encrypt_file


def main():
    STDIN = "/dev/stdin"
    STDOUT = "/dev/stdout"
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
    if file == "-":
        file = STDIN
    if (file != STDIN) and (not os.path.isfile(file)):
        print(f"Cannot find file: {file}")
        exit(1)
    if not password:
        print("Must specify a password.")
        exit(1)
    if output:
        if output == "-":
            output = STDOUT
        elif (not yes) and os.path.isfile(output):
            print(f"Output file already exists: {output}")
            exit(1)
        elif (output_directory := os.path.dirname(output)) and (not os.path.isdir(output_directory)):
            print(f"Output file directory does not exist: {output_directory}")
            exit(1)
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
            print("Must specify --encrypt or --decrypt")
            exit(1)
        if (not output) and (not yes_or_no(f"{verb} file {file} in place?")):
            exit(0)
        if debug:
            print(f"{verb}ing file {file} to {tmpfile}")
        elif verbose:
            print(f"{verb}ing file in place: {file}")
        function(file, password, tmpfile)
        if debug:
            print(f"Done {verb.lower()}ing file {file} to {tmpfile}")
        if output:
            file = output
        if debug:
            print(f"Copying file {tmpfile} to: {file}")
        shutil.copy(tmpfile, file)
        if debug:
            print(f"Done copying file {tmpfile} to: {file}")


def main_encrypt():
    sys.argv = ["--encrypt"] + sys.argv[1:]
    main()


def main_decrypt():
    sys.argv = ["--decrypt"] + sys.argv[1:]
    main()

def _usage():  # noqa
    print("usage: encrypt/decrypt --password password file")
    exit(1)


if __name__ == "__main__":
    sys.argv = sys.argv[1:]
    main()
