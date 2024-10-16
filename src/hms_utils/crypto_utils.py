import base64
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os


def encrypt_file(plaintext_file: str, password: str, encrypted_file: str, prefix: Optional[str] = None) -> bool:
    if not (isinstance(prefix, str) and (prefix := prefix.strip())):
        prefix = b"__HMS_CRYPTO__"
    with open(plaintext_file, "rb") as f:
        data = f.read()
    encrypted_data = Fernet(_derive_key_from_password(password, salt := os.urandom(16))).encrypt(data)
    encrypted_data = prefix + b"\n" + base64.urlsafe_b64encode(salt) + b"\n" + base64.urlsafe_b64encode(encrypted_data)
    with open(f"{encrypted_file}", "wb") as f:
        f.write(encrypted_data)
    return True


def decrypt_file(encrypted_file: str, password: str, decrypted_file: str, prefix: Optional[str] = None) -> bool:
    decrypted_data = read_encrypted_file(encrypted_file, password, prefix=prefix)
    with open(decrypted_file, "wb") as f:
        f.write(decrypted_data)
    return True


def read_encrypted_file(encrypted_file: str, password: str, prefix: Optional[str] = None) -> str:
    with open(encrypted_file, "rb") as f:
        data = f.read().split(b"\n")
    salt, encrypted_data = base64.urlsafe_b64decode(data[1]), base64.urlsafe_b64decode(data[2])
    return Fernet(_derive_key_from_password(password, salt)).decrypt(encrypted_data)


def _derive_key_from_password(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000, backend=default_backend())
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def main():
    import shutil
    import sys
    from dcicutils.command_utils import yes_or_no
    from dcicutils.tmpfile_utils import temporary_file
    def usage():  # noqa
        print("usage: encrypt/decrypt --password password file")
        exit(1)
    file = None ; encrypt = decrypt = False ; password = None ; output = None ; verbose = False # noqa
    argi = 0 ; argn = len(sys.argv)  # noqa
    while argi < argn:
        arg = sys.argv[argi] ; argi += 1  # noqa
        if arg in ["--encrypt", "-encrypt"]:
            encrypt = True
        elif arg in ["--decrypt", "-decrypt"]:
            decrypt = True
        elif arg in ["--password", "-password", "--passwd", "-passwd"]:
            if not ((argi < argn) and (password := sys.argv[argi])):
                usage()
            argi += 1
        elif arg in ["--verbose", "-verbose"]:
            verbose = True
        elif arg in ["--output", "-output", "--out", "-out", "--to", "-to"]:
            if not ((argi < argn) and (output := sys.argv[argi])):
                usage()
            if os.path.exists(output):
                print(f"Output file already exists: {output}")
                exit(1)
            if (output_directory := os.path.dirname(output)) and (not os.path.isdir(output_directory)):
                print(f"Output file directory does not exist: {output_directory}")
                exit(1)
            argi += 1
        else:
            file = arg
    if not password:
        print("Must specify a password.")
        exit(1)
    if not os.path.isfile(file):
        print(f"Cannot find file: {file}")
        exit(1)
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
        if verbose:
            print(f"{verb}ing file {file} to {tmpfile}")
        function(file, password, tmpfile)
        if verbose:
            print(f"Done {verb.lower()}ing file {file} to {tmpfile}")
        if output:
            file = output
        if verbose:
            print(f"Copying file {tmpfile} to: {file}")
        shutil.copy(tmpfile, file)


if __name__ == "__main__":
    main()
