import os
from cryptography.fernet import Fernet

_encryption_key = os.getenv("ENCRYPTION_KEY")
if _encryption_key:
    _cipher = Fernet(_encryption_key.encode() if isinstance(_encryption_key, str) else _encryption_key)
else:
    _cipher = None


def encrypt(text: str) -> str:
    if not _cipher:
        raise RuntimeError("ENCRYPTION_KEY not set in .env")
    return _cipher.encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    if not _cipher:
        raise RuntimeError("ENCRYPTION_KEY not set in .env")
    return _cipher.decrypt(token.encode()).decode()
