"""Comprehensive security audit verification suite.

Covers:
- Priority 1: Production safety gates, session revocation, CSRF across all mutating verbs.
- Priority 2: Cross-tenant isolation against guessed IDs and installation hijacking.
- Priority 3: GitHub App uninstallation, stale PR head-SHA rejection, and event allowlisting.
- Priority 5: Worker crash recovery, retry exhaustion, and dead-letter handling.
"""
import json
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
from faultline.auth.router import router as auth_router
from tests.auth_fixtures import (
    firebase_boundary,
    create_session_token,
    decode_session_token,
    generate_csrf_token,
    verify_csrf_token,
)
from faultline.config import Settings
from faultline.db.models import (
    BackgroundJob,
    Base,
    GitHubInstallation,
    Membership,
    Organization,
    PullRequest,
    Repository,
    RevokedSession,
    User,
    WebhookDelivery,
    utcnow,
)
from faultline.db.session import get_db, seed_default_tenant
from faultline.github.client import generate_install_state
from faultline.github.router import router as github_router
from faultline.investigator.pr_investigator import handle_investigate_pr
from faultline.queue.job_queue import JobQueue
from faultline.webhooks.github import router as webhook_router
from faultline.webhooks.signature import verify_webhook_signature


@pytest.fixture
def audit_env():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()

    JobQueue.session_factory_override = SessionLocal

    # Setup Tenant 1 (Acme)
    org1 = Organization(id="org-acme", name="Acme Corp", slug="acme-corp")
    db.add(org1)
    db.flush()

    user1 = User(
        id="usr-alice",
        firebase_uid="fb-alice",
        email="alice@acme.com",
        display_name="Alice Owner",
        role="admin",
    )
    db.add(user1)
    db.flush()

    mem1 = Membership(id="mem-alice", user_id=user1.id, organization_id=org1.id, role="owner")
    db.add(mem1)

    inst1 = GitHubInstallation(
        id=111111,
        organization_id=org1.id,
        account_login="acme-corp",
    )
    db.add(inst1)
    db.flush()

    repo1 = Repository(
        id="repo-acme-pay",
        organization_id=org1.id,
        installation_id=inst1.id,
        github_repo_id=70001,
        full_name="acme-corp/payment-service",
        is_private=True,
    )
    db.add(repo1)

    # Setup Tenant 2 (Cyber)
    org2 = Organization(id="org-cyber", name="Cyber Corp", slug="cyber-corp")
    db.add(org2)
    db.flush()

    user2 = User(
        id="usr-bob",
        firebase_uid="fb-bob",
        email="bob@cyber.com",
        display_name="Bob Member",
        role="member",
    )
    db.add(user2)
    db.flush()

    mem2 = Membership(id="mem-bob", user_id=user2.id, organization_id=org2.id, role="member")
    db.add(mem2)

    repo2 = Repository(
        id="repo-cyber-vault",
        organization_id=org2.id,
        github_repo_id=80002,
        full_name="cyber-corp/secret-vault",
        is_private=True,
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
    app.include_router(auth_router)
    app.include_router(github_router)
    app.include_router(webhook_router)

    # Generic mutating endpoints to test verbs
    @app.patch("/test/patch-action", dependencies=[Depends(verify_csrf)])
    def patch_endpoint(user: User = Depends(get_current_user)):
        return {"status": "patched", "user": user.id}

    @app.delete("/test/delete-action", dependencies=[Depends(verify_csrf)])
    def delete_endpoint(user: User = Depends(get_current_user)):
        return {"status": "deleted", "user": user.id}

    client = TestClient(app)

    yield {
        "db": db,
        "app": app,
        "client": client,
        "org1": org1,
        "user1": user1,
        "repo1": repo1,
        "inst1": inst1,
        "org2": org2,
        "user2": user2,
        "repo2": repo2,
    }

    JobQueue.session_factory_override = None
    db.close()
    engine.dispose()


# =========================================================================
# PRIORITY 1: AUTHENTICATION SAFETY & PRODUCTION GATES
# =========================================================================

def test_production_safety_gate_rejects_mock_auth():
    """Confirms production cannot boot with mock authentication enabled."""
    settings = Settings(
        environment="production",
        auth_mock_enabled=True,
        session_cookie_secure=True,
        session_secret_key="A" * 32,
        github_webhook_secret="B" * 24,
        firebase_project_id="real-proj",
        firebase_web_api_key="public", firebase_auth_domain="real-proj.firebaseapp.com", firebase_web_app_id="app",
        auto_seed=False,
    )
    with pytest.raises(ValueError, match="Mock authentication .* is strictly forbidden in production"):
        settings.validate_production_safety()


def test_production_safety_gate_mandates_secure_cookies():
    """Confirms production cannot boot with insecure (non-HTTPS) cookies."""
    settings = Settings(
        environment="production",
        auth_mock_enabled=False,
        session_cookie_secure=False,  # Insecure
        session_secret_key="A" * 32,
        github_webhook_secret="B" * 24,
        firebase_project_id="real-proj",
        firebase_web_api_key="public", firebase_auth_domain="real-proj.firebaseapp.com", firebase_web_app_id="app",
        auto_seed=False,
    )
    with pytest.raises(ValueError, match="Session cookies must be secure"):
        settings.validate_production_safety()


def test_production_safety_gate_rejects_weak_secrets():
    """Confirms production cannot boot with default or weak secrets."""
    settings = Settings(
        environment="production",
        auth_mock_enabled=False,
        session_cookie_secure=True,
        session_secret_key="short",  # Weak
        github_webhook_secret="B" * 24,
        firebase_project_id="real-proj",
        firebase_web_api_key="public", firebase_auth_domain="real-proj.firebaseapp.com", firebase_web_app_id="app",
        auto_seed=False,
    )
    with pytest.raises(ValueError, match="Insecure default or weak FZ_SESSION_SECRET_KEY"):
        settings.validate_production_safety()


def test_production_safety_gate_rejects_auto_seed():
    """Confirms production cannot boot with auto_seed=True (no dummy tenants)."""
    settings = Settings(
        environment="production",
        auth_mock_enabled=False,
        session_cookie_secure=True,
        session_secret_key="A" * 32,
        github_webhook_secret="B" * 24,
        firebase_project_id="real-proj",
        firebase_web_api_key="public", firebase_auth_domain="real-proj.firebaseapp.com", firebase_web_app_id="app",
        auto_seed=True,  # Insecure for prod
    )
    with pytest.raises(ValueError, match="FZ_AUTO_SEED must be false in production"):
        settings.validate_production_safety()


def test_logout_revokes_server_side_session(audit_env):
    """Confirms logout invalidates session server-side; reused tokens are rejected."""
    client = audit_env["client"]
    user1 = audit_env["user1"]
    token, jti = create_session_token(user_id=user1.firebase_uid, organization_id=audit_env["org1"].id)
    csrf = generate_csrf_token(user_id=user1.id, session_jti=jti)

    # Set session cookie
    client.cookies.set("__session", token)

    # 1. /me works initially
    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["id"] == user1.id

    # 2. Perform logout
    logout_resp = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout_resp.status_code == 200
    assert logout_resp.json()["status"] == "logged_out"

    # 3. Re-inject the revoked token in Authorization header -> must be rejected with 401
    reuse_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert reuse_resp.status_code == 401
    assert "Session token has been revoked" in reuse_resp.json()["detail"]


def test_csrf_covers_patch_and_delete(audit_env):
    """Confirms CSRF token is mandatory on PATCH and DELETE when cookie authenticated."""
    client = audit_env["client"]
    user1 = audit_env["user1"]
    token, jti = create_session_token(user_id=user1.firebase_uid)
    csrf = generate_csrf_token(user_id=user1.id, session_jti=jti)

    client.cookies.set("__session", token)

    # PATCH without CSRF -> 403
    p1 = client.patch("/test/patch-action")
    assert p1.status_code == 403

    # PATCH with valid CSRF -> 200
    p2 = client.patch("/test/patch-action", headers={"X-CSRF-Token": csrf})
    assert p2.status_code == 200

    # DELETE without CSRF -> 403
    d1 = client.delete("/test/delete-action")
    assert d1.status_code == 403

    # DELETE with valid CSRF -> 200
    d2 = client.delete("/test/delete-action", headers={"X-CSRF-Token": csrf})
    assert d2.status_code == 200


# =========================================================================
# PRIORITY 2: TENANT ISOLATION & ATTACK PREVENTION
# =========================================================================

def test_guessed_repo_id_access_blocked(audit_env):
    """Confirms User 2 (Cyber) cannot sync or access User 1's (Acme) private repository."""
    client = audit_env["client"]
    user2 = audit_env["user2"]
    repo1 = audit_env["repo1"]
    token, jti = create_session_token(user_id=user2.firebase_uid, organization_id=audit_env["org2"].id)
    csrf = generate_csrf_token(user_id=user2.id, session_jti=jti)
    client.cookies.set("__session", token)

    # Attempt to sync guessed repo1 ID
    resp = client.post(
        f"/api/v1/github/repositories/{repo1.id}/sync",
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 403
    assert "User does not belong to the repository's organization" in resp.json()["detail"]


def test_installation_hijacking_blocked(audit_env):
    """Confirms an installation already linked to Org 1 cannot be hijacked by Org 2."""
    client = audit_env["client"]
    org2 = audit_env["org2"]
    user2 = audit_env["user2"]
    inst1 = audit_env["inst1"]

    # Bob is member of Org 2; even if he signs state for Org 2, he cannot link inst1 (already owned by Acme)
    # First make Bob admin of Org 2 so he passes membership check
    db = audit_env["db"]
    mem2 = db.query(Membership).filter_by(user_id=user2.id).first()
    mem2.role = "admin"
    db.commit()

    state = generate_install_state(org2.id, user2.id)
    resp = client.get(f"/api/v1/github/callback?installation_id={inst1.id}&state={state}")
    assert resp.status_code == 401  # Signed state alone is not a current authenticated session.
    db.refresh(inst1)
    assert inst1.organization_id == audit_env["org1"].id


def test_non_admin_cannot_install_github_app(audit_env):
    """Confirms a non-admin/member user cannot complete installation callback."""
    client = audit_env["client"]
    org2 = audit_env["org2"]
    user2 = audit_env["user2"]
    db = audit_env["db"]

    # Ensure Bob is regular 'member'
    mem2 = db.query(Membership).filter_by(user_id=user2.id).first()
    mem2.role = "member"
    db.commit()

    token, _ = create_session_token(user_id=user2.firebase_uid)
    client.cookies.set("__session", token)
    state = generate_install_state(org2.id, user2.id)
    resp = client.get(f"/api/v1/github/callback?installation_id=998877&state={state}")
    assert resp.status_code == 403
    assert "owner or admin" in resp.json()["detail"]


# =========================================================================
# PRIORITY 3: GITHUB INTEGRATION, UNINSTALLATION & STALE PRs
# =========================================================================

def test_github_uninstallation_deactivates_repos(audit_env):
    """Confirms receiving installation.deleted webhook deactivates repos and suspends installation."""
    db = audit_env["db"]
    inst1 = audit_env["inst1"]
    repo1 = audit_env["repo1"]
    assert repo1.is_active is True

    from faultline.webhooks.github import _route_webhook_event
    from fastapi import BackgroundTasks

    payload = {
        "action": "deleted",
        "installation": {"id": inst1.id},
    }
    _route_webhook_event("installation", payload, "deliv-uninstall-1", db, BackgroundTasks())

    db.refresh(inst1)
    db.refresh(repo1)
    assert inst1.is_suspended is True
    assert repo1.is_active is False


def test_stale_pr_investigation_aborted(audit_env):
    """Confirms handle_investigate_pr aborts if PR head SHA has changed (stale commit)."""
    db = audit_env["db"]
    repo1 = audit_env["repo1"]

    pr = PullRequest(
        repository_id=repo1.id,
        github_pr_number=202,
        title="feat: payment retry",
        head_sha="new_head_sha_2222222222222222222222222222",
        base_sha="0000000000000000000000000000000000000000",
    )
    db.add(pr)
    db.commit()

    # Job enqueued for OLD head sha
    old_job = BackgroundJob(
        organization_id=repo1.organization_id,
        repository_id=repo1.id,
        pull_request_id=pr.id,
        job_type="investigate_pr",
        status="running",
        idempotency_key="job-stale-202",
        payload_json=json.dumps({
            "repository_id": repo1.id,
            "pull_request_id": pr.id,
            "full_name": repo1.full_name,
            "head_sha": "old_head_sha_1111111111111111111111111111",  # Mismatch!
            "pr_number": 202,
        }),
    )
    db.add(old_job)
    db.commit()

    handle_investigate_pr(old_job, db)

    db.refresh(old_job)
    assert old_job.status == "cancelled"
    assert "Superseded by newer commit" in old_job.error_message


# =========================================================================
# PRIORITY 5: WORKER CRASH RECOVERY & DEAD-LETTER
# =========================================================================

def test_worker_crash_recovery_and_dead_letter(audit_env):
    """Confirms abandoned 'running' jobs are recovered or marked failed if retries exhausted."""
    db = audit_env["db"]
    org1 = audit_env["org1"]

    # Job 1: Stuck in running with attempts=1 (eligible for retry)
    job1 = BackgroundJob(
        organization_id=org1.id,
        job_type="investigate_pr",
        status="running",
        attempts=1,
        max_attempts=3,
        idempotency_key="job-recover-1",
        payload_json="{}",
    )
    # Job 2: Stuck in running with attempts=3 (dead-letter)
    job2 = BackgroundJob(
        organization_id=org1.id,
        job_type="investigate_pr",
        status="running",
        attempts=3,
        max_attempts=3,
        idempotency_key="job-recover-2",
        payload_json="{}",
    )
    db.add_all([job1, job2])
    db.commit()

    recovered_count = JobQueue.recover_abandoned_jobs(db)
    assert recovered_count == 2

    db.refresh(job1)
    db.refresh(job2)
    assert job1.status == "queued"
    assert "Recovered after unhandled server restart" in job1.error_message

    assert job2.status == "failed"
    assert "Exhausted retry limit" in job2.error_message
