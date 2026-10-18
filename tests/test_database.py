"""Tests for multi-tenant relational database models and sessions."""
import os
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from faultline.db.models import (
    Base,
    User,
    Organization,
    Membership,
    GitHubInstallation,
    Repository,
    PullRequest,
    Investigation,
    WebhookDelivery,
    BackgroundJob,
    AuditEvent,
)
from faultline.db.session import init_db, seed_default_tenant


@pytest.fixture
def db_session():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    test_url = f"sqlite:///{db_path}"
    engine = create_engine(test_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except OSError:
                pass


def test_seed_default_tenant(db_session):
    user, org = seed_default_tenant(db_session)
    assert user.email == "developer@faultlinezero.local"
    assert org.slug == "default-org"

    # Verify membership
    mem = (
        db_session.query(Membership)
        .filter_by(user_id=user.id, organization_id=org.id)
        .first()
    )
    assert mem is not None
    assert mem.role == "owner"


def test_full_saas_hierarchy(db_session):
    org = Organization(name="Acme Corp", slug="acme-corp", billing_tier="pro")
    db_session.add(org)
    db_session.flush()

    user = User(
        firebase_uid="fb-user-123",
        email="alice@acme.com",
        display_name="Alice Architect",
        role="member",
    )
    db_session.add(user)
    db_session.flush()

    membership = Membership(user_id=user.id, organization_id=org.id, role="admin")
    db_session.add(membership)

    installation = GitHubInstallation(
        id=98765432,
        organization_id=org.id,
        account_login="acme-corp",
        account_type="Organization",
        permissions_json='{"pull_requests": "write", "checks": "write"}',
    )
    db_session.add(installation)
    db_session.flush()

    repo = Repository(
        organization_id=org.id,
        installation_id=installation.id,
        github_repo_id=11223344,
        full_name="acme-corp/payment-service",
        is_private=True,
    )
    db_session.add(repo)
    db_session.flush()

    pr = PullRequest(
        repository_id=repo.id,
        github_pr_number=42,
        title="feat: switch payment gateway",
        head_branch="feat/gateway",
        head_sha="a" * 40,
        base_branch="main",
        base_sha="b" * 40,
        author_login="alice",
    )
    db_session.add(pr)
    db_session.flush()

    investigation = Investigation(
        repository_id=repo.id,
        pull_request_id=pr.id,
        commit_sha=pr.head_sha,
        status="completed",
        verdict="REPRODUCED",
        confidence="HIGH",
        summary="Double-capture regression discovered in payment idempotency",
    )
    db_session.add(investigation)

    webhook = WebhookDelivery(
        delivery_id="deliv-uuid-001",
        event_name="pull_request",
        payload_hash="hash123",
        status="processed",
    )
    db_session.add(webhook)

    job = BackgroundJob(
        organization_id=org.id,
        repository_id=repo.id,
        pull_request_id=pr.id,
        job_type="investigate_pr",
        status="completed",
        idempotency_key="job-idem-42",
        payload_json='{"pr_number": 42}',
    )
    db_session.add(job)

    audit = AuditEvent(
        organization_id=org.id,
        user_id=user.id,
        action="repository.synced",
        resource_type="Repository",
        resource_id=repo.id,
    )
    db_session.add(audit)
    db_session.commit()

    # Query and assert relationships
    queried_org = db_session.query(Organization).filter_by(slug="acme-corp").first()
    assert len(queried_org.repositories) == 1
    assert queried_org.repositories[0].full_name == "acme-corp/payment-service"
    assert len(queried_org.repositories[0].pull_requests) == 1
    assert len(queried_org.repositories[0].pull_requests[0].investigations) == 1
    assert (
        queried_org.repositories[0].pull_requests[0].investigations[0].verdict
        == "REPRODUCED"
    )
