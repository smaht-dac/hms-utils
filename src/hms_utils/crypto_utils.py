import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os


def encrypt_file(plaintext_file: str, password: str, encrypted_file: str) -> bool:
    with open(plaintext_file, "rb") as f:
        data = f.read()
    encrypted_data = Fernet(_derive_key_from_password(password, salt := os.urandom(16))).encrypt(data)
    encrypted_data = base64.urlsafe_b64encode(salt) + b"\n" + base64.urlsafe_b64encode(encrypted_data)
    with open(f"{encrypted_file}", "wb") as f:
        f.write(encrypted_data)
    return True


def decrypt_file(encrypted_file: str, password: str, decrypted_file: str) -> bool:
    with open(encrypted_file, "rb") as f:
        data = f.read().split(b"\n")
    salt, encrypted_data = base64.urlsafe_b64decode(data[0]), base64.urlsafe_b64decode(data[1])
    decrypted_data = Fernet(_derive_key_from_password(password, salt)).decrypt(encrypted_data)
    with open(decrypted_file, "wb") as f:
        f.write(decrypted_data)
    return True


def _derive_key_from_password(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000, backend=default_backend())
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))
