"""Cross-tenant security test suite verifying absolute data isolation between organizations."""
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from faultline.auth.dependencies import (
    get_authorized_org,
    get_authorized_repo,
    get_current_user,
)
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
)
from faultline.db.session import get_db
from faultline.github.router import router as github_router


@pytest.fixture
def multi_tenant_env():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()

    # --- Tenant 1: Alpha Corp ---
    org_a = Organization(id="org-alpha", name="Alpha Corp", slug="alpha-corp")
    db.add(org_a)
    db.flush()

    user_a = User(
        id="usr-alice",
        firebase_uid="fb-alice-1",
        email="alice@alpha.corp",
        display_name="Alice (Alpha)",
        role="member",
    )
    db.add(user_a)
    db.flush()

    mem_a = Membership(id="mem-a", user_id=user_a.id, organization_id=org_a.id, role="owner")
    db.add(mem_a)

    inst_a = GitHubInstallation(
        id=101010,
        organization_id=org_a.id,
        account_login="alpha-corp",
    )
    db.add(inst_a)
    db.flush()

    repo_a = Repository(
        id="repo-alpha-core",
        organization_id=org_a.id,
        installation_id=inst_a.id,
        github_repo_id=10001,
        full_name="alpha-corp/core-service",
    )
    db.add(repo_a)

    # --- Tenant 2: Beta Corp ---
    org_b = Organization(id="org-beta", name="Beta Corp", slug="beta-corp")
    db.add(org_b)
    db.flush()

    user_b = User(
        id="usr-bob",
        firebase_uid="fb-bob-2",
        email="bob@beta.corp",
        display_name="Bob (Beta)",
        role="member",
    )
    db.add(user_b)
    db.flush()

    mem_b = Membership(id="mem-b", user_id=user_b.id, organization_id=org_b.id, role="owner")
    db.add(mem_b)

    inst_b = GitHubInstallation(
        id=202020,
        organization_id=org_b.id,
        account_login="beta-corp",
    )
    db.add(inst_b)
    db.flush()

    repo_b = Repository(
        id="repo-beta-billing",
        organization_id=org_b.id,
        installation_id=inst_b.id,
        github_repo_id=20002,
        full_name="beta-corp/billing-service",
    )
    db.add(repo_b)

    db.commit()

    # Build FastAPI app with GitHub router
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

    # Helper to create authenticated client for a user
    def make_client(user: User, org: Organization) -> tuple[TestClient, str]:
        c = TestClient(app)
        token, jti = create_session_token(user_id=user.firebase_uid, organization_id=org.id)
        csrf = generate_csrf_token(user_id=user.id, session_jti=jti)
        c.cookies.set("__session", token)
        return c, csrf

    client_a, csrf_a = make_client(user_a, org_a)
    client_b, csrf_b = make_client(user_b, org_b)

    yield {
        "db": db,
        "client_a": client_a,
        "csrf_a": csrf_a,
        "user_a": user_a,
        "org_a": org_a,
        "repo_a": repo_a,
        "client_b": client_b,
        "csrf_b": csrf_b,
        "user_b": user_b,
        "org_b": org_b,
        "repo_b": repo_b,
    }

    db.close()
    engine.dispose()


def test_repository_listing_strictly_tenant_scoped(multi_tenant_env):
    client_a = multi_tenant_env["client_a"]
    client_b = multi_tenant_env["client_b"]

    # Alice should see Alpha repos only
    resp_a = client_a.get("/api/v1/github/repositories")
    assert resp_a.status_code == 200
    repos_a = [r["full_name"] for r in resp_a.json()]
    assert "alpha-corp/core-service" in repos_a
    assert "beta-corp/billing-service" not in repos_a

    # Bob should see Beta repos only
    resp_b = client_b.get("/api/v1/github/repositories")
    assert resp_b.status_code == 200
    repos_b = [r["full_name"] for r in resp_b.json()]
    assert "beta-corp/billing-service" in repos_b
    assert "alpha-corp/core-service" not in repos_b


def test_cross_tenant_repository_sync_blocked(multi_tenant_env):
    client_a = multi_tenant_env["client_a"]
    csrf_a = multi_tenant_env["csrf_a"]
    repo_b = multi_tenant_env["repo_b"]

    # Alice attempts to trigger sync on Bob's repo -> Forbidden 403
    resp = client_a.post(
        f"/api/v1/github/repositories/{repo_b.id}/sync",
        headers={"X-CSRF-Token": csrf_a},
    )
    assert resp.status_code == 403
    assert "User does not belong to the repository's organization" in resp.json()["detail"]


def test_cross_tenant_organization_header_spoofing_blocked(multi_tenant_env):
    client_a = multi_tenant_env["client_a"]
    org_b = multi_tenant_env["org_b"]

    # Alice sends X-Organization-Id for Beta Corp -> Forbidden 403
    resp = client_a.get(
        "/api/v1/github/installations",
        headers={"X-Organization-Id": org_b.id},
    )
    assert resp.status_code == 403
    assert "User is not a member of this organization" in resp.json()["detail"]
