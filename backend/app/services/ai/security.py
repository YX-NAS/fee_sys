import hashlib
import json
import re
import secrets

from app.security import decrypt_text, encrypt_text


def encrypt_credentials(credentials: dict[str, str]) -> str:
    return encrypt_text(json.dumps(credentials, ensure_ascii=True, separators=(",", ":")))


def decrypt_credentials(ciphertext: str) -> dict[str, str]:
    value = json.loads(decrypt_text(ciphertext))
    if not isinstance(value, dict):
        raise ValueError("无效的厂商凭据")
    return {str(k): str(v) for k, v in value.items()}


def generate_gateway_key() -> tuple[str, str, str]:
    plaintext = f"fgw_{secrets.token_urlsafe(36)}"
    return plaintext, plaintext[:16], hash_gateway_key(plaintext)


def hash_gateway_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def sanitize_provider_error(exc: Exception) -> str:
    text = str(exc).replace("\n", " ").strip()
    text = re.sub(r"(?i)(api[_-]?key|secret[_-]?access[_-]?key|authorization)([\"'=:\\s]+)[^,}\\s]+", r"\1\2***", text)
    text = re.sub(r"\b(?:sk|fgw)_[A-Za-z0-9_-]{12,}\b", "***", text)
    return (text or exc.__class__.__name__)[:500]
