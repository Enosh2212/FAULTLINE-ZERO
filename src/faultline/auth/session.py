"""CSRF HMACs bind requests to a Firebase cookie fingerprint. No custom login JWTs."""
import base64
import hmac
import hashlib
from faultline.config import get_settings

def _b64url_encode(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def generate_csrf_token(
    user_id: str, session_jti: str, secret_key: str | None = None
) -> str:
    """Generates an HMAC-SHA256 CSRF token bound to the user and current session."""
    settings = get_settings()
    secret = (secret_key or settings.session_secret_key).encode("utf-8")
    message = f"csrf:{user_id}:{session_jti}".encode("utf-8")
    token_bytes = hmac.new(secret, message, hashlib.sha256).digest()
    return _b64url_encode(token_bytes)


def verify_csrf_token(
    csrf_token: str,
    user_id: str,
    session_jti: str,
    secret_key: str | None = None,
) -> bool:
    """Verifies that the given CSRF token matches the expected hash for this user and session."""
    if not csrf_token:
        return False
    expected = generate_csrf_token(user_id, session_jti, secret_key)
    return hmac.compare_digest(csrf_token, expected)
