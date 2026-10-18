"""Security tests for GitHub Webhook HMAC verification, deduplication, and event processing."""
import hashlib
import hmac
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from faultline.config import get_settings
from faultline.db.models import (
    Base,
    BackgroundJob,
    GitHubInstallation,
    Organization,
    PullRequest,
    Repository,
    WebhookDelivery,
)
from faultline.db.session import get_db
from faultline.github.client import get_github_client
from faultline.investigator.pr_investigator import handle_investigate_pr  # ensures handler registered
from faultline.webhooks.github import router as webhook_router


@pytest.fixture
def webhook_test_env():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()

    from faultline.queue.job_queue import JobQueue
    JobQueue.session_factory_override = SessionLocal

    # Create Org, Installation, and Repo
    org = Organization(id="org-webhook-test", name="Webhook Test Org", slug="webhook-org")
    db.add(org)
    db.flush()

    inst = GitHubInstallation(
        id=778899,
        organization_id=org.id,
        account_login="webhook-org",
        account_type="Organization",
    )
    db.add(inst)
    db.flush()

    repo = Repository(
        id="repo-wh-1",
        organization_id=org.id,
        installation_id=inst.id,
        github_repo_id=50001,
        full_name="webhook-org/billing-service",
        is_private=True,
    )
    db.add(repo)
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
    app.include_router(webhook_router)
    client = TestClient(app)

    yield {
        "db": db,
        "app": app,
        "client": client,
        "org": org,
        "repo": repo,
        "installation": inst,
        "secret": get_settings().github_webhook_secret,
    }

    db.close()
    JobQueue.session_factory_override = None
    engine.dispose()


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


def test_missing_signature_rejected(webhook_test_env):
    client = webhook_test_env["client"]
    body = json.dumps({"action": "ping"}).encode("utf-8")
    resp = client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 401
    assert "Invalid webhook signature" in resp.json()["detail"]


def test_tampered_signature_rejected(webhook_test_env):
    client = webhook_test_env["client"]
    secret = webhook_test_env["secret"]
    body = json.dumps({"action": "ping"}).encode("utf-8")
    valid_sig = _sign_payload(body, secret)
    bad_sig = valid_sig[:-4] + "dead"

    resp = client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": bad_sig,
        },
    )
    assert resp.status_code == 401
    assert "Invalid webhook signature" in resp.json()["detail"]


def test_valid_ping_delivery_and_deduplication(webhook_test_env):
    client = webhook_test_env["client"]
    secret = webhook_test_env["secret"]
    db = webhook_test_env["db"]

    body = json.dumps({"zen": "Keep it logically awesome."}).encode("utf-8")
    sig = _sign_payload(body, secret)
    delivery_id = "test-delivery-ping-001"

    # 1. First delivery -> Accepted 202
    resp1 = client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig,
            "X-GitHub-Delivery": delivery_id,
            "X-GitHub-Event": "ping",
        },
    )
    assert resp1.status_code == 202
    assert resp1.json()["status"] == "accepted"

    # Verify delivery record saved in DB
    deliv = db.query(WebhookDelivery).filter_by(delivery_id=delivery_id).first()
    assert deliv is not None
    assert deliv.status == "processed"

    # 2. Duplicate delivery -> Idempotent 200 already_processed
    resp2 = client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig,
            "X-GitHub-Delivery": delivery_id,
            "X-GitHub-Event": "ping",
        },
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "already_processed"


def test_pull_request_event_and_stale_cancellation(webhook_test_env):
    client = webhook_test_env["client"]
    secret = webhook_test_env["secret"]
    db = webhook_test_env["db"]

    # 1. PR Opened Event
    pr_opened_payload = {
        "action": "opened",
        "number": 101,
        "pull_request": {
            "number": 101,
            "title": "fix: switch payment gateway retry logic",
            "head": {"sha": "1111111111111111111111111111111111111111", "ref": "fix/payment"},
            "base": {"sha": "0000000000000000000000000000000000000000", "ref": "main"},
            "user": {"login": "alice"},
            "state": "open",
        },
        "repository": {
            "id": 50001,
            "full_name": "webhook-org/billing-service",
            "private": True,
            "default_branch": "main",
        },
        "installation": {"id": 778899},
    }
    body1 = json.dumps(pr_opened_payload).encode("utf-8")
    sig1 = _sign_payload(body1, secret)

    resp1 = client.post(
        "/api/v1/webhooks/github",
        content=body1,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig1,
            "X-GitHub-Delivery": "delivery-pr-open-101",
            "X-GitHub-Event": "pull_request",
        },
    )
    assert resp1.status_code == 202

    # Verify PR record created
    pr = db.query(PullRequest).filter_by(github_pr_number=101).first()
    assert pr is not None
    assert pr.head_sha == "1111111111111111111111111111111111111111"

    # Verify job created
    jobs = db.query(BackgroundJob).filter_by(pull_request_id=pr.id).all()
    assert len(jobs) >= 1

    # 2. PR Synchronize Event (new commit pushed to PR)
    pr_sync_payload = {
        "action": "synchronize",
        "number": 101,
        "pull_request": {
            "number": 101,
            "title": "fix: switch payment gateway retry logic",
            "head": {"sha": "2222222222222222222222222222222222222222", "ref": "fix/payment"},
            "base": {"sha": "0000000000000000000000000000000000000000", "ref": "main"},
            "user": {"login": "alice"},
            "state": "open",
        },
        "repository": {
            "id": 50001,
            "full_name": "webhook-org/billing-service",
            "private": True,
            "default_branch": "main",
        },
        "installation": {"id": 778899},
    }
    body2 = json.dumps(pr_sync_payload).encode("utf-8")
    sig2 = _sign_payload(body2, secret)

    resp2 = client.post(
        "/api/v1/webhooks/github",
        content=body2,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig2,
            "X-GitHub-Delivery": "delivery-pr-sync-101",
            "X-GitHub-Event": "pull_request",
        },
    )
    assert resp2.status_code == 202

    # Verify PR head_sha updated to newest commit
    db.refresh(pr)
    assert pr.head_sha == "2222222222222222222222222222222222222222"


def test_installation_webhook_cannot_assign_workspace_or_add_authorized_repos(webhook_test_env):
    client, db, secret = (webhook_test_env[k] for k in ("client", "db", "secret"))
    def deliver(event, payload, delivery):
        body = json.dumps(payload).encode()
        return client.post("/api/v1/webhooks/github", content=body, headers={
            "Content-Type": "application/json", "X-Hub-Signature-256": _sign_payload(body, secret),
            "X-GitHub-Delivery": delivery, "X-GitHub-Event": event})
    response = deliver("installation", {"action": "created", "installation": {"id": 998877, "account": {"login": "webhook-org"}},
                        "repositories": [{"id": 60001, "full_name": "webhook-org/unauthorized"}]}, "new-installation")
    assert response.status_code == 202
    assert db.query(GitHubInstallation).filter_by(id=998877).first() is None
    assert db.query(Repository).filter_by(github_repo_id=60001).first() is None
    response = deliver("installation_repositories", {"action": "added", "installation": {"id": 778899},
                        "repositories_added": [{"id": 60002, "full_name": "webhook-org/not-selected"}]}, "not-selected")
    assert response.status_code == 202
    assert db.query(Repository).filter_by(github_repo_id=60002).first() is None
    response = deliver("installation_repositories", {"action": "removed", "installation": {"id": 778899},
                        "repositories_removed": [{"id": 50001}]}, "remove-authorized")
    assert response.status_code == 202
    db.expire_all()
    assert db.query(Repository).filter_by(github_repo_id=50001).one().is_active is False


def test_unprovisioned_installation_pull_request_is_acknowledged_without_linking(webhook_test_env, monkeypatch):
    """
    Regression Test for GitHub Webhook 500 error:
    Confirms an inbound pull_request event with an installation_id that does NOT yet exist
    in github_installations is acknowledged without creating an unauthorized workspace connection.
    """
    from faultline.github.client import GitHubAppClient
    monkeypatch.setattr("faultline.github.client._global_github_client", GitHubAppClient(mock_mode=True))

    client = webhook_test_env["client"]
    secret = webhook_test_env["secret"]
    db = webhook_test_env["db"]

    # Use the real IDs observed in the live incident
    unseen_inst_id = 172633902
    unseen_gh_repo_id = 1295366718
    repo_full_name = "Enosh2212/risklens-ai"

    # Verify installation does NOT exist before webhook
    assert db.query(GitHubInstallation).filter_by(id=unseen_inst_id).first() is None

    payload = {
        "action": "opened",
        "installation": {"id": unseen_inst_id},
        "repository": {
            "id": unseen_gh_repo_id,
            "full_name": repo_full_name,
            "private": False,
            "default_branch": "main",
            "owner": {"login": "Enosh2212", "type": "User"},
        },
        "pull_request": {
            "number": 1,
            "title": "test: verify FAULTLINE ZERO live PR investigation",
            "state": "open",
            "head": {"sha": "3333333333333333333333333333333333333333", "ref": "test/faultline-live-investigation"},
            "base": {"sha": "4444444444444444444444444444444444444444", "ref": "main"},
            "user": {"login": "Enosh2212"},
        },
    }

    body = json.dumps(payload).encode("utf-8")
    sig = _sign_payload(body, secret)
    resp = client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig,
            "X-GitHub-Delivery": "delivery-unprovisioned-inst-172633902",
            "X-GitHub-Event": "pull_request",
        },
    )

    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"

    # No workspace can be assigned from an inbound installation ID alone.
    assert db.query(GitHubInstallation).filter_by(id=unseen_inst_id).first() is None
    assert db.query(Repository).filter_by(github_repo_id=unseen_gh_repo_id).first() is None



def test_webhook_routing_error_rolls_back_and_marks_delivery_failed_without_pending_rollback_error(
    webhook_test_env, monkeypatch
):
    """
    Regression Test for PendingRollbackError:
    Confirms an unhandled exception during event routing rolls back cleanly,
    updates WebhookDelivery.status = 'failed', and does NOT raise PendingRollbackError.
    """
    from faultline.webhooks import github as github_wh_module

    def mock_broken_router(event, payload, delivery_id, db, bg_tasks):
        # Force a database flush error / rollback state
        raise RuntimeError("Simulated internal routing fault")

    monkeypatch.setattr(github_wh_module, "_route_webhook_event", mock_broken_router)

    client = webhook_test_env["client"]
    secret = webhook_test_env["secret"]
    db = webhook_test_env["db"]

    payload = {"zen": "Testing exception rollback"}
    body = json.dumps(payload).encode("utf-8")
    sig = _sign_payload(body, secret)
    delivery_id = "delivery-simulate-fault-001"

    resp = client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig,
            "X-GitHub-Delivery": delivery_id,
            "X-GitHub-Event": "ping",
        },
    )

    # Must return 202 with processing_error rather than HTTP 500
    assert resp.status_code == 202
    assert resp.json()["status"] == "processing_error"
    assert "Simulated internal routing fault" not in resp.json()["detail"]

    # Delivery record must be marked 'failed'
    deliv = db.query(WebhookDelivery).filter_by(delivery_id=delivery_id).first()
    assert deliv is not None
    assert deliv.status == "failed"
    assert "Simulated internal routing fault" in deliv.error_message


def test_risklens_pr_investigation_reports_inconclusive_verdict(webhook_test_env, monkeypatch):
    """
    Confirms RiskLens AI PRs report honest INCONCLUSIVE / neutral check run verdict
    when no matching invariant coverage exists in the FalkorDB knowledge graph.
    """
    from faultline.github.client import GitHubAppClient
    from faultline.investigator.pr_investigator import handle_investigate_pr, format_check_run_markdown

    mock_gh = GitHubAppClient(mock_mode=True)
    monkeypatch.setattr("faultline.github.client._global_github_client", mock_gh)

    db = webhook_test_env["db"]

    # Create Org, Installation, and Repo for RiskLens AI
    org = Organization(id="org-risklens", name="RiskLens AI", slug="risklens-ai")
    db.add(org)
    db.flush()

    inst = GitHubInstallation(id=172633902, organization_id=org.id, account_login="Enosh2212")
    db.add(inst)
    db.flush()

    repo = Repository(
        id="repo-risklens-1",
        organization_id=org.id,
        installation_id=inst.id,
        github_repo_id=1295366718,
        full_name="Enosh2212/risklens-ai",
        is_private=False,
    )
    db.add(repo)
    db.flush()

    pr = PullRequest(
        id="pr-risklens-1",
        repository_id=repo.id,
        github_pr_number=1,
        title="test: verify FAULTLINE ZERO live PR investigation",
        head_sha="abcdef1234567890abcdef1234567890abcdef12",
        base_sha="0000000000000000000000000000000000000000",
        state="open",
    )
    db.add(pr)
    db.flush()

    job = BackgroundJob(
        id="job-risklens-inv-1",
        organization_id=org.id,
        repository_id=repo.id,
        pull_request_id=pr.id,
        job_type="investigate_pr",
        idempotency_key="job-risklens-inv-1",
        status="running",
        payload_json=json.dumps({
            "repository_id": repo.id,
            "pull_request_id": pr.id,
            "full_name": repo.full_name,
            "head_sha": pr.head_sha,
            "base_sha": pr.base_sha,
            "pr_number": pr.github_pr_number,
            "check_run_id": 999111,
            "installation_id": inst.id,
        }),
    )
    db.add(job)
    db.commit()

    handle_investigate_pr(job, db)

    # Check investigation record
    from faultline.db.models import Investigation
    inv = db.query(Investigation).filter_by(repository_id=repo.id, commit_sha=pr.head_sha).first()
    assert inv is not None
    assert inv.status == "completed"
    assert inv.verdict == "INCONCLUSIVE"
    assert "no applicable verified business invariants" in inv.summary

    # Check check run formatting
    title, conclusion, text = format_check_run_markdown(
        verdict=inv.verdict,
        pr_number=1,
        head_sha=pr.head_sha,
        invariant_id=None,
        affected_services=[],
        summary=inv.summary,
        cypher_path="test-path",
    )
    assert conclusion == "neutral"
    assert "Untested Invariant Scope" in title
    assert "Inconclusive" in text


