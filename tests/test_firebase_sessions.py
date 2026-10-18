"""Session integration tests use an explicitly injected Admin boundary, never live OAuth."""
import hashlib
import time
from dataclasses import replace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import faultline.auth.router as routes
import faultline.auth.dependencies as deps
import faultline.auth.firebase as firebase
from faultline.config import Settings
from faultline.db.models import Base, User, Organization, Membership
from faultline.db.session import get_db

@pytest.fixture
def env(monkeypatch):
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine)
    def database():
        with factory() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
    settings=Settings(firebase_project_id="faultime-66bce",auth_mock_enabled=False)
    monkeypatch.setattr(routes,"get_settings",lambda:settings)
    claims={"uid":"firebase-user", "email":"test@example.com","email_verified":True,"auth_time":time.time(),"exp":time.time()+3600}
    monkeypatch.setattr(routes,"verify_firebase_id_token",lambda token:dict(claims))
    monkeypatch.setattr(routes,"create_firebase_session",lambda token:"firebase-session-fixture")
    def verify(cookie):
        if cookie!="firebase-session-fixture":raise ValueError("Invalid cookie")
        return dict(claims)
    monkeypatch.setattr(deps,"verify_firebase_session",verify)
    app=FastAPI();app.include_router(routes.router);app.dependency_overrides[get_db]=database
    client=TestClient(app)
    csrf=client.get("/api/v1/auth/csrf").json()["csrf_token"]
    headers={"Origin":"http://localhost:8000","X-CSRF-Token":csrf}
    yield client,claims,headers,factory
    engine.dispose()

def exchange(env,**body):
    client,_,headers,_=env
    return client.post("/api/v1/auth/session",json={"id_token":"test-id-token",**body},headers=headers)

def test_session_cookie_logout_replay_and_private_org(env):
    client,_,_,factory=env
    response=exchange(env)
    assert response.status_code==200,response.text
    cookie=response.cookies["__session"]
    assert cookie=="firebase-session-fixture"
    assert "HttpOnly" in response.headers["set-cookie"] and "SameSite=lax" in response.headers["set-cookie"]
    me=client.get("/api/v1/auth/me").json()
    assert me["current_organization"]["slug"].startswith("workspace-")
    assert me["current_organization"]["role"]=="owner"
    assert client.post("/api/v1/auth/logout").status_code==403
    assert client.post("/api/v1/auth/logout",headers={"X-CSRF-Token":me["csrf_token"]}).status_code==200
    client.cookies.set("__session",cookie)
    assert client.get("/api/v1/auth/me").status_code==401

@pytest.mark.parametrize("changes,code",[({"email_verified":False},403),({"auth_time":0},401),({"auth_time":time.time()+1000},401)])
def test_unverified_and_stale_identities_rejected(env,changes,code):
    env[1].update(changes)
    response=exchange(env)
    assert response.status_code==code
    assert "__session" not in response.cookies

def test_no_cross_tenant_autojoin(env):
    with env[3]() as db:
        db.add(Organization(name="Other",slug="other"));db.commit()
    assert exchange(env,organization_slug="other").status_code==403
    with env[3]() as db:assert db.query(User).count()==0

@pytest.mark.parametrize("headers",[{}, {"Origin":"https://evil.example"},{"Origin":"http://localhost:8000","X-CSRF-Token":"wrong"}])
def test_login_csrf(env,headers):
    response=env[0].post("/api/v1/auth/session",json={"id_token":"anything"},headers=headers)
    assert response.status_code==403

def test_unconfigured_admin_fails_closed(env,monkeypatch):
    def unavailable(token):raise firebase.AuthConfigurationError("private path must stay hidden")
    monkeypatch.setattr(routes,"verify_firebase_id_token",unavailable)
    response=exchange(env)
    assert response.status_code==503
    assert "private path" not in response.text
    assert "__session" not in response.cookies

def test_custom_bearer_not_accepted(env):
    assert env[0].get("/api/v1/auth/me",headers={"Authorization":"Bearer custom-jwt"}).status_code==401

def test_forged_cookie_rejected(env):
    env[0].cookies.set("__session","forged-cookie")
    assert env[0].get("/api/v1/auth/me").status_code==401

def test_no_mock_or_unsigned_fallback(monkeypatch):
    firebase.get_admin_app.cache_clear()
    monkeypatch.setattr(firebase,"get_settings",lambda:Settings(auth_mock_enabled=True))
    with pytest.raises(firebase.AuthConfigurationError):firebase.verify_firebase_id_token("mock:admin:test@example.com")
    firebase.get_admin_app.cache_clear()

def test_production_settings_validation_is_reached(monkeypatch):
    from faultline.config import get_settings
    monkeypatch.setenv("FZ_ENV","production")
    monkeypatch.setenv("FZ_AUTH_MOCK_ENABLED","true")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError,match="Mock authentication"):get_settings()
    finally:get_settings.cache_clear()


def test_admin_adapter_uses_revocation_checks(monkeypatch):
    import sys
    from types import SimpleNamespace
    calls=[]
    auth=SimpleNamespace(
        verify_id_token=lambda token,**kwargs:calls.append(("id",kwargs)) or {"uid":"u"},
        verify_session_cookie=lambda cookie,**kwargs:calls.append(("session",kwargs)) or {"uid":"u"},
        create_session_cookie=lambda token,**kwargs:calls.append(("create",kwargs)) or b"firebase-cookie")
    monkeypatch.setitem(sys.modules,"firebase_admin",SimpleNamespace(auth=auth))
    monkeypatch.setattr(firebase,"get_admin_app",lambda:"configured-app")
    firebase.verify_firebase_id_token("id")
    firebase.verify_firebase_session("cookie")
    assert firebase.create_firebase_session("id")=="firebase-cookie"
    assert calls[0][1]["check_revoked"] is True
    assert calls[1][1]["check_revoked"] is True
    assert calls[2][1]["expires_in"]==5*86400

def test_production_startup_requires_admin(monkeypatch):
    import asyncio
    import faultline.api as api
    def unavailable():raise firebase.AuthConfigurationError("No ADC")
    monkeypatch.setattr(api,"settings",Settings(environment="production"))
    monkeypatch.setattr(firebase,"get_admin_app",unavailable)
    async def startup():
        async with api.lifespan(api.app):pass
    with pytest.raises(firebase.AuthConfigurationError):asyncio.run(startup())

def test_workspace_redirects_without_session():
    import faultline.api as api
    response=TestClient(api.app).get("/workspace",follow_redirects=False)
    assert response.status_code==303
    assert response.headers["location"].startswith("/login")


def test_google_sign_in_flow(env):
    client, claims, headers, factory = env
    claims.update({
        "uid": "google-oauth-uid-12345",
        "email": "developer@gmail.com",
        "email_verified": True,
        "name": "Google Developer",
        "picture": "https://lh3.googleusercontent.com/photo.jpg",
        "auth_time": time.time(),
        "exp": time.time() + 3600,
    })
    resp = client.post("/api/v1/auth/session", json={"id_token": "google-token"}, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["user"]["firebase_uid"] == "google-oauth-uid-12345"
    assert data["user"]["email"] == "developer@gmail.com"
    assert data["user"]["display_name"] == "Google Developer"
    assert data["user"]["avatar_url"] == "https://lh3.googleusercontent.com/photo.jpg"
    assert data["organization"]["role"] == "owner"
    assert "csrf_token" in data

    # Verify protected /me endpoint with session cookie
    me = client.get("/api/v1/auth/me").json()
    assert me["user"]["firebase_uid"] == "google-oauth-uid-12345"
    assert me["current_organization"]["role"] == "owner"


def test_github_sign_in_flow(env):
    client, claims, headers, factory = env
    claims.update({
        "uid": "github-oauth-uid-67890",
        "email": "octocat@github.com",
        "email_verified": True,
        "name": "The Octocat",
        "picture": "https://avatars.githubusercontent.com/u/583231",
        "auth_time": time.time(),
        "exp": time.time() + 3600,
    })
    resp = client.post("/api/v1/auth/session", json={"id_token": "github-token"}, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["user"]["firebase_uid"] == "github-oauth-uid-67890"
    assert data["user"]["email"] == "octocat@github.com"
    assert data["user"]["display_name"] == "The Octocat"

    # Verify protected /me endpoint
    me = client.get("/api/v1/auth/me").json()
    assert me["user"]["firebase_uid"] == "github-oauth-uid-67890"


def test_google_application_credentials_env_resolution(monkeypatch, tmp_path):
    from faultline.config import get_settings
    fake_cred = tmp_path / "fake-service-account.json"
    fake_cred.write_text('{"project_id": "faultime-66bce"}')
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(fake_cred))
    monkeypatch.delenv("FZ_FIREBASE_CREDENTIALS_PATH", raising=False)
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert s.firebase_credentials_path == str(fake_cred)
        assert s.firebase_project_id == "faultime-66bce"
    finally:
        get_settings.cache_clear()


def test_project_id_mismatch_fails_closed(monkeypatch, tmp_path):
    from faultline.config import Settings
    from types import SimpleNamespace
    import sys

    # Simulate credentials object with mismatched project_id
    fake_cred = SimpleNamespace(
        project_id="other-malicious-project",
        get_credential=lambda: True,
    )
    fake_credentials_module = SimpleNamespace(
        Certificate=lambda path: fake_cred,
        ApplicationDefault=lambda: fake_cred,
    )
    monkeypatch.setitem(sys.modules, "firebase_admin.credentials", fake_credentials_module)
    monkeypatch.setattr(
        firebase,
        "get_settings",
        lambda: Settings(firebase_project_id="faultime-66bce", firebase_credentials_path="/fake/path.json"),
    )
    firebase.get_admin_app.cache_clear()
    try:
        with pytest.raises(firebase.AuthConfigurationError, match="project does not match"):
            firebase.get_admin_app()
    finally:
        firebase.get_admin_app.cache_clear()

