"""Authentication and authorization package for FAULTLINE ZERO SaaS."""
from faultline.auth.dependencies import (
    get_authorized_org,
    get_authorized_repo,
    get_current_user,
    get_optional_user,
    verify_csrf,
)
from faultline.auth.firebase import verify_firebase_id_token
from faultline.auth.session import (
    generate_csrf_token,
    verify_csrf_token,
)

__all__ = [
    "generate_csrf_token",
    "verify_csrf_token",
    "verify_firebase_id_token",
    "get_current_user",
    "get_optional_user",
    "get_authorized_org",
    "get_authorized_repo",
    "verify_csrf",
]
