from cryptography.fernet import Fernet
from app.config import settings


def _get_fernet() -> Fernet:
    key = settings.cruvai_encryption_key
    if not key:
        raise RuntimeError(
            "CRUVAI_ENCRYPTION_KEY not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value. Returns a string (not bytes) for DB storage."""
    encrypted = _get_fernet().encrypt(plaintext.encode("utf-8"))
    return encrypted.decode("utf-8")


def decrypt_value(ciphertext: str | bytes) -> str:
    """Decrypt an encrypted value. Accepts both str and bytes."""
    if isinstance(ciphertext, str):
        ciphertext = ciphertext.encode("utf-8")
    return _get_fernet().decrypt(ciphertext).decode("utf-8")
