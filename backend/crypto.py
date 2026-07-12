import os
from base64 import urlsafe_b64encode
from fastapi import HTTPException
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import json

# Stable PBKDF2 params — DO NOT change after user sessions/passwords are stored.
_PBKDF2_ITERATIONS = 390_000
_fernet_cache = None


def _config_error(msg: str):
    return HTTPException(status_code=503, detail=f"Ошибка конфигурации шифрования: {msg}")


def get_fernet() -> Fernet:
    """Build a Fernet from ENCRYPTION_KEY + FERNET_SALT. Fail clearly if missing.
    Never auto-generates values (would make stored secrets undecryptable)."""
    global _fernet_cache
    if _fernet_cache is not None:
        return _fernet_cache
    key = os.environ.get("ENCRYPTION_KEY")
    salt = os.environ.get("FERNET_SALT")
    if not key or not salt:
        raise _config_error(
            "не заданы ENCRYPTION_KEY и/или FERNET_SALT в переменных окружения backend."
        )
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=salt.encode("utf-8"), iterations=_PBKDF2_ITERATIONS)
    derived = urlsafe_b64encode(kdf.derive(key.encode("utf-8")))
    _fernet_cache = Fernet(derived)
    return _fernet_cache


def encrypt_dict(data: dict) -> str:
    f = get_fernet()
    return f.encrypt(json.dumps(data).encode("utf-8")).decode("utf-8")


def decrypt_dict(token: str) -> dict:
    f = get_fernet()
    try:
        return json.loads(f.decrypt(token.encode("utf-8")).decode("utf-8"))
    except InvalidToken:
        raise _config_error(
            "не удалось расшифровать сохранённые данные. Вероятно, изменены ENCRYPTION_KEY или FERNET_SALT."
        )
