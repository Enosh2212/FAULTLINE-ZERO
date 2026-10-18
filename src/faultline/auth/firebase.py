"""Firebase Admin is the only identity and session verifier. No token fallbacks."""
from functools import lru_cache
import os
from faultline.config import get_settings

class AuthConfigurationError(RuntimeError):
    pass

@lru_cache(maxsize=1)
def get_admin_app():
    settings = get_settings()
    if settings.auth_mock_enabled:
        raise AuthConfigurationError("Mock authentication must be disabled")
    if not settings.firebase_project_id:
        raise AuthConfigurationError("Firebase project is not configured")
    if settings.is_production and os.getenv("FIREBASE_AUTH_EMULATOR_HOST"):
        raise AuthConfigurationError("Firebase emulator is forbidden in production")
    try:
        import firebase_admin
        from firebase_admin import credentials
        # Reuse existing app instance if already initialized
        try:
            return firebase_admin.get_app("faultline-server")
        except ValueError:
            pass

        cred_path = settings.firebase_credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path and os.path.isfile(cred_path):
            cred = credentials.Certificate(cred_path)
        else:
            cred = credentials.ApplicationDefault()

        resolved = cred.get_credential()
        cred_project = getattr(cred, "project_id", None)
        if cred_project and cred_project != settings.firebase_project_id:
            raise AuthConfigurationError("Firebase credential project does not match configured project")
        if not resolved:
            raise AuthConfigurationError("Firebase Admin credentials are unavailable")
        return firebase_admin.initialize_app(
            cred, {"projectId": settings.firebase_project_id}, name="faultline-server"
        )
    except AuthConfigurationError:
        raise
    except Exception as exc:
        raise AuthConfigurationError("Firebase Admin authentication is not configured") from exc

def admin_ready():
    try:
        get_admin_app()
        return True
    except AuthConfigurationError:
        return False

def verify_firebase_id_token(token):
    app = get_admin_app()
    from firebase_admin import auth
    return auth.verify_id_token(token, app=app, check_revoked=True)

def create_firebase_session(token, seconds=5 * 86400):
    app = get_admin_app()
    from firebase_admin import auth
    cookie = auth.create_session_cookie(token, expires_in=seconds, app=app)
    return cookie.decode() if isinstance(cookie, bytes) else cookie

def verify_firebase_session(cookie):
    app = get_admin_app()
    from firebase_admin import auth
    return auth.verify_session_cookie(cookie, app=app, check_revoked=True)
