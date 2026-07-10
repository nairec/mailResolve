from cryptography.fernet import Fernet, InvalidToken

from src.core.config import settings


def _get_fernet() -> Fernet:
    if not settings.secret_key:
        raise ValueError("SECRET_KEY must be set for token encryption")
    return Fernet(settings.secret_key.encode() if isinstance(settings.secret_key, str) else settings.secret_key)


def encrypt_token(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt token") from exc
