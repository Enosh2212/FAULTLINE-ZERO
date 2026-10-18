"""Security tests for session authentication, token tampering, and CSRF protection."""
import time
import pytest
from fastapi import FastAPI, Depends, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from faultline.auth.dependencies import (
    get_current_user,
    get_authorized_org,
    get_authorized_repo,
    verify_csrf,
)
from tests.auth_fixtures import (
    firebase_boundary,
    create_session_token,
    decode_session_token,
    generate_csrf_token,
    verify_csrf_token,
)
from faultline.db.models import Base, User, Organization, Membership, Repository
from faultline.db.session import get_db


@pytest.fixture
def auth_test_env():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()

    # Create Org 1 and User 1
    org1 = Organization(id="org-1", name="Alpha Corp", slug="alpha-corp")
    db.add(org1)
    db.flush()

    user1 = User(
        id="usr-1",
        firebase_uid="fb-alice",
        email="alice@alpha.com",
        display_name="Alice",
        role="member",
    )
    db.add(user1)
    db.flush()

    mem1 = Membership(id="mem-1", user_id=user1.id, organization_id=org1.id, role="owner")
    db.add(mem1)

    repo1 = Repository(
        id="repo-1",
        organization_id=org1.id,
        github_repo_id=1001,
        full_name="alpha-corp/core-service",
    )
    db.add(repo1)

    # Create Org 2 and User 2 (Cross-tenant setup)
    org2 = Organization(id="org-2", name="Beta Corp", slug="beta-corp")
    db.add(org2)
    db.flush()

    user2 = User(
        id="usr-2",
        firebase_uid="fb-bob",
        email="bob@beta.com",
        display_name="Bob",
        role="member",
    )
    db.add(user2)
    db.flush()

    mem2 = Membership(id="mem-2", user_id=user2.id, organization_id=org2.id, role="owner")
    db.add(mem2)

    repo2 = Repository(
        id="repo-2",
        organization_id=org2.id,
        github_repo_id=2002,
        full_name="beta-corp/billing-service",
    )
    db.add(repo2)

    db.commit()

    # Build FastAPI test app
    app = FastAPI()

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    @app.get("/test/me")
    def me_endpoint(user: User = Depends(get_current_user)):
        return {"id": user.id, "email": user.email}

    @app.post("/test/mutating-action", dependencies=[Depends(verify_csrf)])
    def mutating_endpoint(user: User = Depends(get_current_user)):
        return {"status": "success", "user": user.id}

    @app.get("/test/repos/{repo_id}")
    def repo_endpoint(
        repo_data: tuple[User, Organization, Repository] = Depends(get_authorized_repo),
    ):
        _, org, repo = repo_data
        return {"repo": repo.full_name, "org": org.name}

    client = TestClient(app)

    yield {
        "db": db,
        "app": app,
        "client": client,
        "user1": user1,
        "org1": org1,
        "repo1": repo1,
        "user2": user2,
        "org2": org2,
        "repo2": repo2,
    }

    db.close()
    engine.dispose()


def test_csrf_token_generation_and_validation():
    secret = "csrf-secret-key"
    user_id = "usr-123"
    jti = "jti-abc"

    csrf_token = generate_csrf_token(user_id, jti, secret_key=secret)
    assert verify_csrf_token(csrf_token, user_id, jti, secret_key=secret) is True

    # Reject if wrong user
    assert verify_csrf_token(csrf_token, "usr-999", jti, secret_key=secret) is False
    # Reject if wrong jti
    assert verify_csrf_token(csrf_token, user_id, "different-jti", secret_key=secret) is False
    # Reject if empty
    assert verify_csrf_token("", user_id, jti, secret_key=secret) is False


def test_unauthenticated_request_rejected(auth_test_env):
    client = auth_test_env["client"]
    resp = client.get("/test/me")
    assert resp.status_code == 401
    assert "Authentication credentials were not provided" in resp.json()["detail"]


def test_authenticated_via_firebase_cookie(auth_test_env):
    client = auth_test_env["client"]
    user1 = auth_test_env["user1"]
    token, _ = create_session_token(user_id=user1.firebase_uid)

    client.cookies.set("__session", token)
    resp = client.get("/test/me")
    assert resp.status_code == 200
    assert resp.json()["id"] == user1.id
    assert resp.json()["email"] == user1.email


def test_csrf_protection_on_cookie_mutation(auth_test_env):
    client = auth_test_env["client"]
    user1 = auth_test_env["user1"]
    token, jti = create_session_token(user_id=user1.firebase_uid)
    csrf_token = generate_csrf_token(user_id=user1.id, session_jti=jti)

    # 1. Mutating POST with cookie but NO CSRF token -> Rejected 403
    client.cookies.set("__session", token)
    resp = client.post("/test/mutating-action")
    assert resp.status_code == 403
    assert "CSRF token missing or invalid" in resp.json()["detail"]

    # 2. Mutating POST with cookie and valid CSRF token -> Allowed 200
    resp = client.post(
        "/test/mutating-action",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


