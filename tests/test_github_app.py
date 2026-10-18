"""Tests for GitHub App state signing, installation onboarding, and repository management."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tests.auth_fixtures import firebase_boundary, create_session_token, generate_csrf_token
from faultline.db.models import (
    AuditEvent,
    BackgroundJob,
    Base,
    GitHubInstallation,
    Investigation,
    Membership,
    Organization,
    PullRequest,
    Repository,
    User,
    WorkspaceInstallation,
)
from faultline.db.session import get_db
from faultline.github.client import (
    GitHubAppClient,
    generate_install_state,
    verify_install_state,
)
from faultline.github.router import router as github_router


@pytest.fixture
def gh_app_env():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()

    # Create Organization & User
    org = Organization(id="org-acme", name="Acme Labs", slug="acme-labs")
    db.add(org)
    db.flush()

    user = User(
        id="usr-alice",
        firebase_uid="fb-alice",
        email="alice@acme.com",
        display_name="Alice",
    )
    db.add(user)
    db.flush()

    mem = Membership(id="mem-alice", user_id=user.id, organization_id=org.id, role="owner")
    db.add(mem)
    db.commit()

    app = FastAPI()

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.include_router(github_router)
    client = TestClient(app)

    token, jti = create_session_token(user_id=user.firebase_uid, organization_id=org.id)
    csrf_token = generate_csrf_token(user_id=user.id, session_jti=jti)
    client.cookies.set("__session", token)

    yield {
        "db": db,
        "app": app,
        "client": client,
        "org": org,
        "user": user,
        "csrf_token": csrf_token,
    }

    db.close()
    engine.dispose()


def test_install_state_cryptography():
    state = generate_install_state("org-123", "usr-456", secret_key="test-secret", expires_in=60)
    data = verify_install_state(state, secret_key="test-secret")
    assert data["org_id"] == "org-123"
    assert data["user_id"] == "usr-456"

    # Signature tampering
    parts = state.split(".")
    tampered = f"{parts[0]}.badsignature"
    with pytest.raises(ValueError, match="Installation state signature mismatch"):
        verify_install_state(tampered, secret_key="test-secret")

    # Expiration
    expired_state = generate_install_state(
        "org-123", "usr-456", secret_key="test-secret", expires_in=-10
    )
    with pytest.raises(ValueError, match="Installation state expired"):
        verify_install_state(expired_state, secret_key="test-secret")


def test_github_app_mock_client():
    gh = GitHubAppClient(mock_mode=True)
    jwt_token = gh.generate_app_jwt()
    assert jwt_token == "mock-github-app-jwt"

    token = gh.get_installation_access_token(12345)
    assert "ghs_mock_installation_token_12345" in token

    repos = gh.list_installation_repositories(12345)
    assert len(repos) >= 2
    assert repos[0]["full_name"] == "acme-corp/payment-gateway"

    # Test Checks API
    cr = gh.create_check_run(
        installation_id=12345,
        owner="acme-corp",
        repo="payment-gateway",
        name="FAULTLINE ZERO",
        head_sha="abcdef123456",
        status="in_progress",
    )
    assert cr["id"] > 0
    assert cr["status"] == "in_progress"

    updated = gh.update_check_run(
        installation_id=12345,
        owner="acme-corp",
        repo="payment-gateway",
        check_run_id=cr["id"],
        status="completed",
        conclusion="success",
        title="Verification Clean",
        summary="No regressions detected",
    )
    assert updated["status"] == "completed"
    assert updated["conclusion"] == "success"


def test_install_url_fails_closed_without_credentials(gh_app_env, monkeypatch):
    monkeypatch.setattr("faultline.github.client._global_github_client", GitHubAppClient(mock_mode=True))
    response = gh_app_env["client"].get("/api/v1/github/install/url")
    assert response.status_code == 503


def test_unverified_redirect_never_links_installation(gh_app_env):
    state = generate_install_state(gh_app_env["org"].id, gh_app_env["user"].id)
    response = gh_app_env["client"].get("/api/v1/github/callback", params={"installation_id": 554433, "state": state})
    assert response.status_code == 400
    assert gh_app_env["db"].query(GitHubInstallation).count() == 0
    assert gh_app_env["client"].get("/api/v1/github/repositories").json() == []


def test_rsa_pem_real_jwt_generation_and_verification():
    import jwt
    import time
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    # Generate real RSA private key
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_private = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    pem_public = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    # Initialize client with real RSA key and App ID
    gh_client = GitHubAppClient(app_id=987654, private_key=pem_private, mock_mode=False)
    jwt_token = gh_client.generate_app_jwt()
    assert jwt_token is not None
    assert jwt_token != "mock-github-app-jwt"

    # Decode and verify with public key
    decoded = jwt.decode(jwt_token, pem_public, algorithms=["RS256"])
    assert decoded["iss"] == "987654"
    assert decoded["exp"] > time.time()


def test_token_caching_and_auto_refresh(monkeypatch):
    import time
    gh_client = GitHubAppClient(app_id=12345, private_key="dummy-key", mock_mode=False)

    call_count = 0
    def fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        class FakeResponse:
            def raise_for_status(self): pass
            def json(self):
                return {
                    "token": f"ghs_token_call_{call_count}",
                    "expires_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 3600)),
                }
        return FakeResponse()

    monkeypatch.setattr(gh_client, "generate_app_jwt", lambda: "fake-jwt")
    import httpx
    monkeypatch.setattr(httpx.Client, "post", fake_post)

    # 1. First call fetches new token
    t1 = gh_client.get_installation_access_token(99001)
    assert t1 == "ghs_token_call_1"
    assert call_count == 1

    # 2. Immediate second call returns cached token without HTTP request
    t2 = gh_client.get_installation_access_token(99001)
    assert t2 == "ghs_token_call_1"
    assert call_count == 1

    # 3. Simulate token expiring soon (less than 300s left) -> triggers auto-refresh
    gh_client._installation_tokens[99001]["expires_at"] = time.time() + 100
    t3 = gh_client.get_installation_access_token(99001)
    assert t3 == "ghs_token_call_2"
    assert call_count == 2


def test_pr_files_and_content_fetching():
    gh_client = GitHubAppClient(mock_mode=True)
    files = gh_client.get_pr_files(12345, "acme-corp", "payment-gateway", 42)
    assert len(files) >= 1
    assert "filename" in files[0]

    content = gh_client.get_file_content(12345, "acme-corp", "payment-gateway", "src/payment/gateway.py", "abc1234")
    assert content is not None
    assert "process_transaction" in content

