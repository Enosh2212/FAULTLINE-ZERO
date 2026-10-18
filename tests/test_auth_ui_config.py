"""Public auth configuration must never expose server secrets or enable mock sign-in."""
from dataclasses import replace
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import faultline.auth.router as auth_router
from faultline.config import Settings


def client_for(monkeypatch, settings, admin_available=True):
    monkeypatch.setattr(auth_router, "get_settings", lambda: settings)
    monkeypatch.setattr(auth_router, "admin_ready", lambda: admin_available)
    app = FastAPI()
    app.include_router(auth_router.router)
    return TestClient(app)


def ready_settings():
    return Settings(
        firebase_web_api_key="public-browser-key",
        firebase_auth_domain="example.firebaseapp.com",
        firebase_project_id="example-project",
        firebase_web_app_id="public-app-id",
        firebase_github_enabled=True,
        auth_mock_enabled=False,
        session_secret_key="SERVER-SESSION-SECRET-DO-NOT-PUBLISH",
        firebase_credentials_path="/private/service-account.json",
        github_client_secret="SERVER-GITHUB-SECRET-DO-NOT-PUBLISH",
    )


def test_only_browser_configuration_is_published(monkeypatch):
    response = client_for(monkeypatch, ready_settings()).get("/api/v1/auth/config")
    payload = response.json()
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert payload["configured"] is True
    assert payload["providers"] == {"github": True, "google": False}
    assert payload["email_password"] is True
    assert {"apiKey", "authDomain", "projectId", "appId"} <= set(payload["firebase"])
    assert "SERVER-" not in response.text
    assert "/private/" not in response.text


def test_mock_auth_is_never_advertised_as_real_provider_auth(monkeypatch):
    client = client_for(monkeypatch, replace(ready_settings(), auth_mock_enabled=True))
    payload = client.get("/api/v1/auth/config").json()
    assert payload["configured"] is False
    assert payload["firebase"] is None
    assert not any(payload["providers"].values())


def test_missing_admin_disables_sessions_but_preserves_client_flows(monkeypatch):
    payload = client_for(monkeypatch, ready_settings(), False).get("/api/v1/auth/config").json()
    assert payload["configured"] is True
    assert payload["server_session_ready"] is False


def test_unconfigured_local_demo_exposes_no_firebase_credentials(monkeypatch):
    payload = client_for(monkeypatch, Settings()).get("/api/v1/auth/config").json()
    assert payload["configured"] is False
    assert payload["firebase"] is None
    assert payload["providers"] == {"github": False, "google": False}
