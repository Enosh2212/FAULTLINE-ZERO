"""Explicit test-only Admin boundary fixture; never imported by application code."""
import hashlib
import secrets
import time
import pytest
from faultline.auth.session import generate_csrf_token, verify_csrf_token

TOKENS = {}
def create_session_token(user_id, **kwargs):
    token = secrets.token_urlsafe(48)
    TOKENS[token] = {"uid": user_id, "exp": time.time() + 3600, "email_verified": True}
    return token, hashlib.sha256(token.encode()).hexdigest()

def decode_session_token(token, **kwargs):
    if token not in TOKENS: raise ValueError("Invalid Firebase fixture cookie")
    return TOKENS[token]

@pytest.fixture(autouse=True)
def firebase_boundary(monkeypatch):
    import faultline.auth.dependencies as dependencies
    monkeypatch.setattr(dependencies, "verify_firebase_session", decode_session_token)
    yield
    TOKENS.clear()
