import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings


def _derive_fernet_key() -> bytes:
    """
    Returns a valid 32-byte urlsafe base64 Fernet key.
    Uses CREDENTIAL_ENCRYPTION_KEY if explicitly configured; in dev/test derives deterministically
    from SECRET_KEY via SHA-256. Production requires CREDENTIAL_ENCRYPTION_KEY explicitly.
    """
    configured = (settings.CREDENTIAL_ENCRYPTION_KEY or "").strip()
    if configured:
        try:
            # Accept an already valid Fernet key directly
            Fernet(configured.encode("utf-8"))
            return configured.encode("utf-8")
        except Exception:
            # Derive a 32-byte key from arbitrary passphrase
            digest = hashlib.sha256(configured.encode("utf-8")).digest()
            return base64.urlsafe_b64encode(digest)

    digest = hashlib.sha256(f"acttrident-fernet:{settings.SECRET_KEY}".encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(plaintext: Optional[str]) -> Optional[str]:
    """Encrypts a sensitive credential string with Fernet authenticated encryption."""
    if not plaintext:
        return None
    if plaintext.startswith("enc:v1:"):
        return plaintext
    f = Fernet(_derive_fernet_key())
    token = f.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"enc:v1:{token}"


def decrypt_secret(ciphertext: Optional[str]) -> Optional[str]:
    """Decrypts a Fernet-encrypted credential. Supports legacy unencrypted values safely during migration."""
    if not ciphertext:
        return None
    if not ciphertext.startswith("enc:v1:"):
        return ciphertext
    raw = ciphertext[len("enc:v1:"):]
    f = Fernet(_derive_fernet_key())
    try:
        return f.decrypt(raw.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None


def mask_secret(value: Optional[str]) -> str:
    """Returns a non-sensitive masked indicator for UI/API responses without exposing secret material."""
    if not value:
        return ""
    plain = decrypt_secret(value) if value.startswith("enc:v1:") else value
    if not plain:
        return "********"
    if len(plain) <= 4:
        return "****"
    return f"{'*' * 8}{plain[-4:]}"
