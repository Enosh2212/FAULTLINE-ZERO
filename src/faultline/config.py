"""Environment-driven application configuration."""
from dataclasses import dataclass
from functools import lru_cache
import os
import json
from pathlib import Path


def _load_env_file() -> None:
    for base in [Path.cwd(), Path(__file__).resolve().parents[2]]:
        env_file = base / ".env"
        if env_file.exists():
            try:
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip("'\"")
                        if k and k not in os.environ and v:
                            os.environ[k] = v
            except Exception:
                pass
            break


_load_env_file()


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"true", "1", "yes"}



@dataclass(frozen=True)
class Settings:
    graph_host: str = "localhost"
    graph_port: int = 6379
    graph_name: str = "faultline_zero"
    graph_password: str | None = None
    api_key: str | None = None
    auto_seed: bool = True
    allowed_origins: tuple[str, ...] = ("http://localhost:8000", "http://127.0.0.1:8000")
    runner_timeout: int = 8
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    fly_memory_enabled: bool = False
    fly_memory_top_k: int = 5
    fly_memory_seed: int = 42

    # Environment & Deployment Mode
    environment: str = "development"

    # SaaS & Authentication settings
    database_url: str = "sqlite:///./faultline_zero.db"
    firebase_project_id: str | None = None
    firebase_credentials_path: str | None = None
    firebase_web_api_key: str | None = None
    firebase_auth_domain: str | None = None
    firebase_web_app_id: str | None = None
    firebase_github_enabled: bool = False
    firebase_google_enabled: bool = False
    session_secret_key: str = "faultline-zero-dev-secret-key-change-in-prod-32b"
    session_cookie_name: str = "__session"
    session_cookie_secure: bool = False
    auth_mock_enabled: bool = False

    # GitHub App Integration settings
    github_app_id: int | None = None
    github_app_private_key: str | None = None
    github_app_private_key_path: str | None = None
    github_webhook_secret: str = "dev-webhook-secret"
    github_client_id: str | None = None
    github_client_secret: str | None = None

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"production", "prod"}

    def validate_production_safety(self) -> None:
        """Enforces zero-tolerance security gate checks for production deployment."""
        if not self.is_production:
            return

        if self.auth_mock_enabled:
            raise ValueError(
                "SECURITY GATE VIOLATION: Mock authentication (FZ_AUTH_MOCK_ENABLED) is strictly forbidden in production."
            )
        if not self.session_cookie_secure:
            raise ValueError(
                "SECURITY GATE VIOLATION: Session cookies must be secure (FZ_SESSION_COOKIE_SECURE=true) in production to mandate HTTPS."
            )
        if (
            self.session_secret_key == "faultline-zero-dev-secret-key-change-in-prod-32b"
            or len(self.session_secret_key) < 32
        ):
            raise ValueError(
                "SECURITY GATE VIOLATION: Insecure default or weak FZ_SESSION_SECRET_KEY detected in production environment."
            )
        if (
            self.github_webhook_secret == "dev-webhook-secret"
            or len(self.github_webhook_secret) < 20
        ):
            raise ValueError(
                "SECURITY GATE VIOLATION: Insecure default or weak FZ_GITHUB_WEBHOOK_SECRET detected in production environment."
            )
        if not all((self.firebase_project_id, self.firebase_web_api_key, self.firebase_auth_domain, self.firebase_web_app_id)):
            raise ValueError(
                "SECURITY GATE VIOLATION: Real Firebase credentials must be configured in production environment."
            )
        if self.auto_seed:
            raise ValueError(
                "SECURITY GATE VIOLATION: FZ_AUTO_SEED must be false in production to prevent dummy tenant seeding."
            )



@lru_cache(maxsize=1)
def get_settings() -> Settings:
    public_firebase = json.loads((Path(__file__).parent / "web/firebase-config.json").read_text())
    s = Settings(
        graph_host=os.getenv("FZ_GRAPH_HOST", "localhost"),
        graph_port=int(os.getenv("FZ_GRAPH_PORT", "6379")),
        graph_name=os.getenv("FZ_GRAPH_NAME", "faultline_zero"),
        graph_password=os.getenv("FZ_GRAPH_PASSWORD") or None,
        api_key=os.getenv("FZ_API_KEY") or None,
        auto_seed=_bool("FZ_AUTO_SEED", True),
        allowed_origins=tuple(x.strip() for x in os.getenv(
            "FZ_ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
        ).split(",") if x.strip()),
        runner_timeout=max(1, min(int(os.getenv("FZ_RUNNER_TIMEOUT", "8")), 25)),
        llm_api_key=os.getenv("FZ_LLM_API_KEY") or None,
        llm_base_url=os.getenv("FZ_LLM_BASE_URL") or None,
        llm_model=os.getenv("FZ_LLM_MODEL") or None,
        fly_memory_enabled=_bool("FZ_FLY_MEMORY_ENABLED", False),
        fly_memory_top_k=int(os.getenv("FZ_FLY_MEMORY_TOP_K", "5")),
        fly_memory_seed=int(os.getenv("FZ_FLY_MEMORY_SEED", "42")),
        database_url=os.getenv("FZ_DATABASE_URL", "sqlite:///./faultline_zero.db"),
        firebase_project_id=os.getenv("FZ_FIREBASE_PROJECT_ID") or public_firebase["projectId"],
        firebase_credentials_path=(
            os.getenv("FZ_FIREBASE_CREDENTIALS_PATH")
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            or None
        ),
        firebase_web_api_key=os.getenv("FZ_FIREBASE_WEB_API_KEY") or public_firebase["apiKey"],
        firebase_auth_domain=os.getenv("FZ_FIREBASE_AUTH_DOMAIN") or public_firebase["authDomain"],
        firebase_web_app_id=os.getenv("FZ_FIREBASE_WEB_APP_ID") or public_firebase["appId"],
        firebase_github_enabled=_bool("FZ_FIREBASE_GITHUB_ENABLED", True),
        firebase_google_enabled=_bool("FZ_FIREBASE_GOOGLE_ENABLED", True),
        session_secret_key=os.getenv("FZ_SESSION_SECRET_KEY", "faultline-zero-dev-secret-key-change-in-prod-32b"),
        session_cookie_name=os.getenv("FZ_SESSION_COOKIE_NAME", "__session"),
        session_cookie_secure=_bool("FZ_SESSION_COOKIE_SECURE", False),
        auth_mock_enabled=_bool("FZ_AUTH_MOCK_ENABLED", False),
        github_app_id=int(os.getenv("FZ_GITHUB_APP_ID").strip()) if os.getenv("FZ_GITHUB_APP_ID") and os.getenv("FZ_GITHUB_APP_ID").strip() else None,
        github_app_private_key=os.getenv("FZ_GITHUB_APP_PRIVATE_KEY") or None,
        github_app_private_key_path=os.getenv("FZ_GITHUB_APP_PRIVATE_KEY_PATH") or None,
        github_webhook_secret=os.getenv("FZ_GITHUB_WEBHOOK_SECRET", "dev-webhook-secret"),
        github_client_id=os.getenv("FZ_GITHUB_CLIENT_ID") or None,
        github_client_secret=os.getenv("FZ_GITHUB_CLIENT_SECRET") or None,
        environment=os.getenv("FZ_ENV", "development"),
    )
    s.validate_production_safety()
    return s
