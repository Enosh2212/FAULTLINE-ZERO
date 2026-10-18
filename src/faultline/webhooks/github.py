"""GitHub Webhook receiver endpoint with signature verification, deduplication, and event routing."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from faultline.config import get_settings
from faultline.db.models import (
    GitHubInstallation,
    Organization,
    PullRequest,
    Repository,
    WebhookDelivery,
    WorkspaceInstallation,
    utcnow,
)
from faultline.db.session import get_db
from faultline.github.client import get_github_client
from faultline.queue.job_queue import JobQueue
from faultline.webhooks.signature import verify_webhook_signature

logger = logging.getLogger("faultline.webhooks.github")

router = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks"])


@router.post("/github")
async def receive_github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    x_github_delivery: str | None = Header(None, alias="X-GitHub-Delivery"),
    x_github_event: str | None = Header(None, alias="X-GitHub-Event"),
    db: Session = Depends(get_db),
):
    """
    Receives and validates GitHub webhook deliveries.
    Enforces HMAC-SHA256 signature verification, deduplicates by delivery ID,
    persists delivery records, and dispatches asynchronous investigation jobs.
    """
    settings = get_settings()

    # 1. Read raw body bytes
    body_bytes = await request.body()
    if not body_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty webhook request body",
        )

    # 2. Verify signature
    is_valid = verify_webhook_signature(
        body_bytes, x_hub_signature_256, settings.github_webhook_secret
    )
    if not is_valid:
        logger.warning("Rejected webhook delivery with invalid HMAC signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    delivery_id = x_github_delivery or hashlib.sha256(body_bytes).hexdigest()[:32]
    event_name = x_github_event or "unknown"
    payload_hash = hashlib.sha256(body_bytes).hexdigest()

    # 3. Deduplication check
    existing_delivery = (
        db.query(WebhookDelivery).filter_by(delivery_id=delivery_id).first()
    )
    if existing_delivery:
        logger.info("Delivery %s already processed; acknowledging idempotently", delivery_id)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "already_processed", "delivery_id": delivery_id},
        )

    # 4. Record delivery
    delivery_record = WebhookDelivery(
        delivery_id=delivery_id,
        event_name=event_name,
        payload_hash=payload_hash,
        status="received",
    )
    db.add(delivery_record)
    db.commit()

    # Parse JSON payload
    try:
        payload: Dict[str, Any] = json.loads(body_bytes.decode("utf-8"))
    except Exception as exc:
        delivery_record.status = "failed"
        delivery_record.error_message = f"JSON decode error: {exc}"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON in webhook body",
        ) from exc

    # 5. Route event
    try:
        _route_webhook_event(event_name, payload, delivery_id, db, background_tasks)
        delivery_record.status = "processed"
        delivery_record.processed_at = utcnow()
        db.commit()
    except Exception as exc:
        logger.exception("Error routing webhook event '%s': %s", event_name, exc)
        db.rollback()
        try:
            deliv = db.query(WebhookDelivery).filter_by(delivery_id=delivery_id).first()
            if deliv:
                deliv.status = "failed"
                deliv.error_message = str(exc)[:500]
                db.commit()
        except Exception as inner_exc:
            logger.error("Failed to persist failed webhook delivery status: %s", inner_exc)
            db.rollback()

        # Still return 202 so GitHub does not endlessly retry delivery if it was an internal processing error
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"status": "processing_error", "detail": "Webhook processing failed; check server logs"},
        )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "accepted",
            "delivery_id": delivery_id,
            "event": event_name,
        },
    )


SUPPORTED_WEBHOOK_EVENTS = {
    "ping",
    "installation",
    "installation_repositories",
    "pull_request",
    "check_suite",
    "check_run",
}


def _get_or_create_installation(
    db: Session,
    inst_id: int,
    account_login: str,
    account_type: str = "Organization",
) -> GitHubInstallation | None:
    """Resolve an installation previously verified by the authenticated OAuth flow."""
    inst = db.query(GitHubInstallation).filter_by(id=inst_id).first()
    if inst:
        return inst

    # An HMAC-valid delivery proves the sender, not which local workspace owns
    # an installation. Only the session-bound OAuth flow may establish that link.
    return None


def _route_webhook_event(
    event: str,
    payload: Dict[str, Any],
    delivery_id: str,
    db: Session,
    background_tasks: BackgroundTasks,
) -> None:
    """Internal router for supported GitHub webhook events with strict allowlisting."""
    if event not in SUPPORTED_WEBHOOK_EVENTS:
        logger.info("Ignoring unmonitored webhook event '%s' (delivery %s)", event, delivery_id)
        return

    if event == "ping":
        logger.info("Received GitHub ping event: zen='%s'", payload.get("zen"))
        return

    if event == "installation":
        action = payload.get("action")
        inst_data = payload.get("installation", {})
        inst_id = inst_data.get("id")
        if not inst_id:
            return

        account_login = inst_data.get("account", {}).get("login", "")
        account_type = inst_data.get("account", {}).get("type", "Organization")
        inst = _get_or_create_installation(db, inst_id, account_login, account_type)

        if not inst:
            return

        if action == "created":
            inst.is_suspended = False
            db.commit()
            logger.info("Processed installation created for %s (%d)", account_login, inst_id)
        elif action == "deleted" and inst:
            inst.is_suspended = True
            for repo in inst.repositories:
                repo.is_active = False
            db.commit()
            logger.info("Marked installation %d as deleted and deactivated all repositories", inst_id)
        elif action in {"suspend"} and inst:
            inst.is_suspended = True
            db.commit()
        elif action in {"unsuspend"} and inst:
            inst.is_suspended = False
            db.commit()
        return

    if event == "installation_repositories":
        action = payload.get("action")
        inst_data = payload.get("installation", {})
        inst_id = inst_data.get("id")
        account_login = inst_data.get("account", {}).get("login", "")
        account_type = inst_data.get("account", {}).get("type", "Organization")
        if inst_id:
            inst = _get_or_create_installation(db, inst_id, account_login, account_type)
            if not inst:
                return
            for r_data in payload.get("repositories_removed", []):
                r_id = r_data.get("id")
                repos = db.query(Repository).filter_by(github_repo_id=r_id, installation_id=inst.id).all()
                for repo in repos:
                    repo.is_active = False
            db.commit()
            logger.info("Synchronized installation_repositories %s for installation %d", action, inst_id)
        return

    if event == "pull_request":
        action = payload.get("action")
        pr_data = payload.get("pull_request", {})
        repo_data = payload.get("repository", {})
        installation_data = payload.get("installation", {})
        inst_id = installation_data.get("id")

        if not repo_data or not pr_data:
            return

        gh_repo_id = repo_data.get("id")
        full_name = repo_data.get("full_name")
        owner_data = repo_data.get("owner", {})
        owner_login = owner_data.get("login") or (full_name.split("/")[0] if full_name and "/" in full_name else "")
        account_type = owner_data.get("type", "Organization")

        inst = None
        if inst_id:
            inst = _get_or_create_installation(db, inst_id, owner_login, account_type)
            if not inst:
                return
            if inst.is_suspended:
                logger.warning("Rejected pull_request webhook for suspended installation: %d", inst_id)
                return

        pr_number = pr_data.get("number")
        head_sha = pr_data.get("head", {}).get("sha")
        base_sha = pr_data.get("base", {}).get("sha")
        title = pr_data.get("title", "")
        author = pr_data.get("user", {}).get("login", "")

        # Find all authorized active workspace subscriptions for this repository
        subscribed_repos = (
            db.query(Repository)
            .filter_by(github_repo_id=gh_repo_id, installation_id=inst.id, is_active=True)
            .all()
        )
        if not subscribed_repos:
            logger.info("Ignoring PR for repository %s without an active workspace subscription", full_name)
            return

        check_run_id = None
        if action in {"opened", "synchronize", "reopened"}:
            gh_client = get_github_client()
            owner, repo_name = full_name.split("/", 1) if "/" in full_name else ("", full_name)
            if inst_id and owner and repo_name:
                try:
                    cr = gh_client.create_check_run(
                        installation_id=inst_id,
                        owner=owner,
                        repo=repo_name,
                        name="FAULTLINE ZERO // Pre-Merge Regression Gate",
                        head_sha=head_sha,
                        status="in_progress",
                    )
                    check_run_id = cr.get("id")
                except Exception as exc:
                    logger.warning("Could not create initial GitHub Check Run: %s", exc)

        for repo in subscribed_repos:
            # Verify workspace has a valid WorkspaceInstallation link (or legacy org association)
            ws_link = db.query(WorkspaceInstallation).filter_by(
                organization_id=repo.organization_id, installation_id=inst.id
            ).first()
            if not ws_link and inst.organization_id and inst.organization_id != repo.organization_id:
                continue

            # Find or create PullRequest for this workspace repo
            pr = (
                db.query(PullRequest)
                .filter_by(repository_id=repo.id, github_pr_number=pr_number)
                .first()
            )
            if not pr:
                pr = PullRequest(
                    repository_id=repo.id,
                    github_pr_number=pr_number,
                    title=title,
                    head_branch=pr_data.get("head", {}).get("ref", ""),
                    head_sha=head_sha,
                    base_branch=pr_data.get("base", {}).get("ref", "main"),
                    base_sha=base_sha,
                    author_login=author,
                    state=pr_data.get("state", "open"),
                )
                db.add(pr)
                db.flush()
            else:
                pr.head_sha = head_sha
                pr.base_sha = base_sha
                pr.title = title
                pr.state = pr_data.get("state", pr.state)
                pr.updated_at = utcnow()
                db.flush()

            if action in {"opened", "synchronize", "reopened"}:
                if action == "synchronize":
                    JobQueue.cancel_pr_jobs(db, pr.id)

                job = JobQueue.enqueue(
                    db=db,
                    organization_id=repo.organization_id,
                    job_type="investigate_pr",
                    idempotency_key=f"pr:{repo.organization_id}:{repo.id}:{pr.id}:{head_sha}:{delivery_id}",
                    payload={
                        "repository_id": repo.id,
                        "pull_request_id": pr.id,
                        "full_name": full_name,
                        "head_sha": head_sha,
                        "base_sha": base_sha,
                        "pr_number": pr_number,
                        "check_run_id": check_run_id,
                        "installation_id": inst_id,
                    },
                    repository_id=repo.id,
                    pull_request_id=pr.id,
                )
                background_tasks.add_task(JobQueue.process_job_now, job.id)
                logger.info("Enqueued investigation job %s for PR #%d in workspace %s", job.id, pr_number, repo.organization_id)

            elif action == "closed":
                pr.state = "closed"
                if pr_data.get("merged", False):
                    pr.state = "merged"
                logger.info("Updated PR #%d state to %s", pr_number, pr.state)

        db.commit()
