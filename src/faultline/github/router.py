"""FastAPI router for GitHub App installations, repository onboarding, and synchronization."""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import BackgroundTasks, APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from faultline.auth.dependencies import (
    get_authorized_org,
    get_authorized_repo,
    get_current_user,
    verify_csrf,
)
from faultline.config import get_settings
from faultline.db.models import (
    AuditEvent,
    BackgroundJob,
    GitHubInstallation,
    Membership,
    Organization,
    PullRequest,
    Repository,
    User,
    WorkspaceInstallation,
)
from faultline.db.session import get_db
from faultline.github.client import (
    generate_install_state,
    get_github_client,
    verify_install_state,
)
from faultline.graph_engine import FalkorRepositoryGraph
from faultline.queue.job_queue import JobQueue

logger = logging.getLogger("faultline.github.router")

router = APIRouter(prefix="/api/v1/github", tags=["GitHub App"])


class RepositoryResponseSchema(BaseModel):
    id: str
    organization_id: str
    installation_id: Optional[int]
    github_repo_id: int
    full_name: str
    is_private: bool
    default_branch: str
    is_active: bool
    open_prs_count: int
    indexing_status: Optional[str] = "not_indexed"
    indexed_commit_sha: Optional[str] = None
    indexed_at: Optional[str] = None
    latest_investigation: Optional[Dict[str, Any]] = None


class InstallationResponseSchema(BaseModel):
    id: int
    organization_id: Optional[str]
    account_login: str
    account_type: str
    is_suspended: bool
    installed_at: str
    repositories_count: int


class AvailableRepositorySchema(BaseModel):
    github_repo_id: int
    full_name: str
    account_login: str
    installation_id: int
    is_private: bool
    default_branch: str
    already_added: bool
    is_active: bool
    repo_id: Optional[str] = None
    indexing_status: Optional[str] = None


class BatchAddRepositoriesRequest(BaseModel):
    github_repo_ids: List[int]
    auto_index: bool = False


@router.get("/installations", response_model=List[InstallationResponseSchema])
def list_installations(
    auth_data: tuple[User, Organization, Membership] = Depends(get_authorized_org),
    db: Session = Depends(get_db),
):
    """Lists GitHub App installations linked to the active organization."""
    _, org, _ = auth_data
    ws_insts = db.query(WorkspaceInstallation).filter_by(organization_id=org.id).all()
    ws_inst_ids = {w.installation_id for w in ws_insts}
    
    installations = (
        db.query(GitHubInstallation)
        .filter((GitHubInstallation.id.in_(ws_inst_ids)) | (GitHubInstallation.organization_id == org.id))
        .all()
        if ws_inst_ids
        else db.query(GitHubInstallation).filter_by(organization_id=org.id).all()
    )
    result = []
    for inst in installations:
        repo_count = db.query(Repository).filter_by(organization_id=org.id, installation_id=inst.id, is_active=True).count()
        result.append(
            InstallationResponseSchema(
                id=inst.id,
                organization_id=org.id,
                account_login=inst.account_login,
                account_type=inst.account_type,
                is_suspended=inst.is_suspended,
                installed_at=inst.installed_at.isoformat(),
                repositories_count=repo_count,
            )
        )
    return result


@router.get("/available-repositories", response_model=List[AvailableRepositorySchema])
def get_available_repositories(
    auth_data: tuple[User, Organization, Membership] = Depends(get_authorized_org),
    db: Session = Depends(get_db),
):
    """Returns candidate repositories authorized by the GitHub App and current user for this workspace."""
    _, org, _ = auth_data
    ws_insts = db.query(WorkspaceInstallation).filter_by(organization_id=org.id).all()
    inst_ids = {w.installation_id for w in ws_insts}
    for inst in db.query(GitHubInstallation).filter_by(organization_id=org.id).all():
        inst_ids.add(inst.id)

    existing_repos = {
        r.github_repo_id: r
        for r in db.query(Repository).filter_by(organization_id=org.id).all()
    }

    candidates = {}

    # 1. From authorized candidate repositories recorded during verified OAuth
    for w in ws_insts:
        if w.authorized_repositories_json:
            try:
                raw_list = json.loads(w.authorized_repositories_json)
                inst_obj = db.get(GitHubInstallation, w.installation_id)
                account = inst_obj.account_login if inst_obj else ""
                for item in raw_list:
                    r_id = item["id"]
                    candidates[r_id] = {
                        "github_repo_id": r_id,
                        "full_name": item["full_name"],
                        "account_login": account,
                        "installation_id": w.installation_id,
                        "is_private": item.get("private", True),
                        "default_branch": item.get("default_branch", "main"),
                    }
            except Exception:
                pass

    # 2. From GitHub App client for active installations
    try:
        from faultline.workspace import live_github
        gh_client = live_github()
        for i_id in inst_ids:
            inst_obj = db.get(GitHubInstallation, i_id)
            if inst_obj and not inst_obj.is_suspended:
                remote_list = gh_client.list_installation_repositories(i_id)
                for r in remote_list:
                    r_id = r["id"]
                    if r_id not in candidates:
                        candidates[r_id] = {
                            "github_repo_id": r_id,
                            "full_name": r["full_name"],
                            "account_login": inst_obj.account_login,
                            "installation_id": i_id,
                            "is_private": r.get("private", True),
                            "default_branch": r.get("default_branch", "main"),
                        }
    except Exception:
        pass

    # 3. Include any repositories already connected to this workspace
    for r_id, repo in existing_repos.items():
        if r_id not in candidates:
            inst_login = repo.installation.account_login if repo.installation else ""
            candidates[r_id] = {
                "github_repo_id": r_id,
                "full_name": repo.full_name,
                "account_login": inst_login,
                "installation_id": repo.installation_id or 0,
                "is_private": repo.is_private,
                "default_branch": repo.default_branch,
            }

    result = []
    for r_id, c in candidates.items():
        existing = existing_repos.get(r_id)
        result.append(
            AvailableRepositorySchema(
                github_repo_id=c["github_repo_id"],
                full_name=c["full_name"],
                account_login=c["account_login"],
                installation_id=c["installation_id"],
                is_private=c["is_private"],
                default_branch=c["default_branch"],
                already_added=bool(existing and existing.is_active),
                is_active=bool(existing and existing.is_active),
                repo_id=existing.id if existing else None,
                indexing_status=existing.indexing_status if existing else None,
            )
        )
    return sorted(result, key=lambda x: x.full_name)


@router.post("/repositories/batch-add", dependencies=[Depends(verify_csrf)])
def batch_add_repositories(
    tasks: BackgroundTasks,
    req: BatchAddRepositoriesRequest,
    auth_data: tuple[User, Organization, Membership] = Depends(get_authorized_org),
    db: Session = Depends(get_db),
):
    """Adds authorized repositories to the current workspace with optional immediate indexing."""
    user, org, membership = auth_data
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(403, "Workspace admin access required to add repositories")

    if not req.github_repo_ids:
        raise HTTPException(400, "No repositories selected")

    available = {r.github_repo_id: r for r in get_available_repositories(auth_data, db)}

    added = []
    queued_jobs = []

    for r_id in req.github_repo_ids:
        candidate = available.get(r_id)
        if not candidate:
            continue

        repo = db.query(Repository).filter_by(organization_id=org.id, github_repo_id=r_id).first()
        if not repo:
            repo = Repository(
                organization_id=org.id,
                installation_id=candidate.installation_id,
                github_repo_id=candidate.github_repo_id,
                full_name=candidate.full_name,
                default_branch=candidate.default_branch,
                is_private=candidate.is_private,
                is_active=True,
                indexing_status="unindexed",
            )
            db.add(repo)
            db.flush()
        else:
            repo.is_active = True
            repo.full_name = candidate.full_name
            repo.default_branch = candidate.default_branch
            repo.is_private = candidate.is_private
            repo.installation_id = candidate.installation_id

        added.append(repo)

        if req.auto_index and repo.installation_id:
            try:
                from faultline.workspace import live_github
                live_github()
                revision = repo.default_branch or "HEAD"
                window_bucket = int(time.time() // 30)
                idempotency_key = f"index:{repo.id}:{revision}:{window_bucket}"
                job = JobQueue.enqueue(
                    db=db,
                    organization_id=org.id,
                    job_type="index_repository",
                    idempotency_key=idempotency_key,
                    payload={"repository_id": repo.id, "revision": revision},
                    repository_id=repo.id,
                )
                if job.status in {"queued", "running"}:
                    repo.indexing_status = "queued" if job.status == "queued" else "indexing"
                    queued_jobs.append(job.id)
                    if job.status == "queued":
                        tasks.add_task(JobQueue.process_job_now, job.id)
            except Exception:
                pass

    db.commit()
    return {
        "status": "success",
        "added_count": len(added),
        "repositories": [{"id": r.id, "full_name": r.full_name, "status": r.indexing_status} for r in added],
        "queued_jobs": queued_jobs,
    }


@router.post("/repositories/{repo_id}/remove", dependencies=[Depends(verify_csrf)])
@router.delete("/repositories/{repo_id}", dependencies=[Depends(verify_csrf)])
def remove_repository_from_workspace(
    repo_data: tuple[User, Organization, Repository] = Depends(get_authorized_repo),
    db: Session = Depends(get_db),
):
    """Deactivates a repository in the current workspace without impacting other workspaces."""
    user, org, repo = repo_data
    membership = db.query(Membership).filter_by(user_id=user.id, organization_id=org.id).first()
    if not membership or membership.role not in {"owner", "admin"}:
        raise HTTPException(403, "Workspace admin access required to remove a repository")

    repo.is_active = False

    queued_jobs = db.query(BackgroundJob).filter_by(repository_id=repo.id, status="queued").all()
    for j in queued_jobs:
        j.status = "cancelled"

    db.commit()
    return {"status": "removed", "repository_id": repo.id, "full_name": repo.full_name}


@router.get("/repositories", response_model=List[RepositoryResponseSchema])
def list_repositories(
    auth_data: tuple[User, Organization, Membership] = Depends(get_authorized_org),
    db: Session = Depends(get_db),
):
    """Lists synchronized repositories and their latest regression status."""
    _, org, _ = auth_data
    repos = (
        db.query(Repository)
        .filter_by(organization_id=org.id)
        .order_by(Repository.full_name)
        .all()
    )

    result = []
    for r in repos:
        open_prs = (
            db.query(PullRequest)
            .filter_by(repository_id=r.id, state="open")
            .count()
        )
        latest_inv = None
        if r.investigations:
            sorted_inv = sorted(r.investigations, key=lambda x: x.created_at, reverse=True)
            if sorted_inv:
                inv = sorted_inv[0]
                latest_inv = {
                    "id": inv.id,
                    "commit_sha": inv.commit_sha[:8],
                    "status": inv.status,
                    "verdict": inv.verdict,
                    "confidence": inv.confidence,
                    "summary": inv.summary,
                    "created_at": inv.created_at.isoformat(),
                }

        result.append(
            RepositoryResponseSchema(
                id=r.id,
                organization_id=r.organization_id,
                installation_id=r.installation_id,
                github_repo_id=r.github_repo_id,
                full_name=r.full_name,
                is_private=r.is_private,
                default_branch=r.default_branch,
                is_active=r.is_active,
                open_prs_count=open_prs,
                indexing_status=r.indexing_status or "not_indexed",
                indexed_commit_sha=r.indexed_commit_sha,
                indexed_at=r.indexed_at.isoformat() if r.indexed_at else None,
                latest_investigation=latest_inv,
            )
        )
    return result


@router.get("/connect")
def connect_github(request: Request, auth=Depends(get_authorized_org)):
    """Primary one-click entrypoint to connect GitHub App and import repositories."""
    from faultline.github.onboarding import authorize
    return authorize(request, auth, flow="install")


@router.get("/configure-url")
def get_configure_url(request: Request, response: Response, auth=Depends(get_authorized_org), db: Session = Depends(get_db)):
    """Returns the URL to GitHub installation configuration to grant access to more repositories."""
    from faultline.github.onboarding import configure_url
    return configure_url(request, response, auth, db)


@router.post("/disconnect", dependencies=[Depends(verify_csrf)])
def disconnect_workspace_github(
    auth_data: tuple[User, Organization, Membership] = Depends(get_authorized_org),
    db: Session = Depends(get_db),
):
    """Disconnects GitHub App monitoring from this workspace without deleting physical installation."""
    user, org, membership = auth_data
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(403, "Workspace admin access required to disconnect GitHub")

    repos = db.query(Repository).filter_by(organization_id=org.id).all()
    for r in repos:
        r.is_active = False

    db.query(WorkspaceInstallation).filter_by(organization_id=org.id).delete()
    db.commit()
    return {"status": "disconnected", "organization_id": org.id}


@router.get("/install/url")
def get_install_url(request: Request, response: Response, auth=Depends(get_authorized_org)):
    from faultline.github.onboarding import install_url
    return install_url(request, response, auth)


@router.get("/authorize")
def start_github_authorization(request: Request, auth=Depends(get_authorized_org)):
    from faultline.github.onboarding import authorize
    return authorize(request, auth)


def connection_workspace(request: Request, state: Optional[str] = Query(None), user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Resolve a signed callback's workspace and check the current user's membership."""
    error = request.query_params.get("error")
    if not state:
        if error:
            return (user, None, None)
        raise HTTPException(400, "Missing GitHub connection state")
    try:
        payload = verify_install_state(state)
    except Exception as exc:
        if error:
            return (user, None, None)
        raise HTTPException(400, "Invalid or expired GitHub connection state") from exc
    return get_authorized_org(request, org_id=payload.get("org_id"), user=user, db=db)


@router.get("/callback")
def installation_callback(request: Request, state: Optional[str] = Query(None), auth=Depends(connection_workspace)):
    from faultline.github.onboarding import after_install
    return after_install(request, state, auth)


@router.get("/oauth/callback")
def github_oauth_callback(
    request: Request,
    tasks: BackgroundTasks,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    auth=Depends(connection_workspace),
    db: Session = Depends(get_db),
):
    from faultline.github.onboarding import oauth_callback
    return oauth_callback(request, code, state, auth, db, tasks=tasks)


@router.post("/repositories/{repo_id}/sync", dependencies=[Depends(verify_csrf)])
def sync_repository(
    repo_data: tuple[User, Organization, Repository] = Depends(get_authorized_repo),
    db: Session = Depends(get_db),
):
    """Triggers on-demand synchronization of repository metadata."""
    user, org, repo = repo_data
    if not repo.installation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository is not connected to a GitHub App installation",
        )

    from faultline.workspace import live_github
    gh_client = live_github()
    remote_repos = gh_client.list_installation_repositories(repo.installation_id)
    matched = next((r for r in remote_repos if r["id"] == repo.github_repo_id), None)
    if not matched:
        raise HTTPException(403, "Repository access was revoked. Reauthorize GitHub access.")
    if matched:
        repo.full_name = matched.get("full_name", repo.full_name)
        repo.default_branch = matched.get("default_branch", repo.default_branch)
        repo.is_private = matched.get("private", repo.is_private)
        db.commit()

    return {"status": "synced", "repository": repo.full_name}


class IndexRepositoryRequest(BaseModel):
    revision: Optional[str] = None


@router.post("/repositories/{repo_id}/index", dependencies=[Depends(verify_csrf)])
def index_repository_endpoint(
    tasks: BackgroundTasks,
    repo_data: tuple[User, Organization, Repository] = Depends(get_authorized_repo),
    req: Optional[IndexRepositoryRequest] = None,
    db: Session = Depends(get_db),
):
    """Enqueues on-demand background indexing of repository AST and FalkorDB graph."""
    user, org, repo = repo_data
    if not repo.installation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository is not connected to a GitHub App installation",
        )

    from faultline.workspace import live_github
    live_github()
    if not repo.installation or repo.installation.is_suspended:
        raise HTTPException(409, "GitHub installation access needs reauthorization")
    repo.is_active = True
    revision = (req.revision if req and req.revision else None) or repo.default_branch or "HEAD"
    window_bucket = int(time.time() // 30)
    idempotency_key = f"index:{repo.id}:{revision}:{window_bucket}"

    job = JobQueue.enqueue(
        db=db,
        organization_id=org.id,
        job_type="index_repository",
        idempotency_key=idempotency_key,
        payload={
            "repository_id": repo.id,
            "revision": revision,
        },
        repository_id=repo.id,
    )
    if job.status in {"queued", "running"}:
        repo.indexing_status = "queued" if job.status == "queued" else "indexing"
    db.commit()

    if job.status == "queued":
        tasks.add_task(JobQueue.process_job_now, job.id)
    return {
        "status": "indexing_queued",
        "job_id": job.id,
        "repository": repo.full_name,
        "revision": revision,
    }


@router.get("/repositories/{repo_id}/graph")
def get_repository_graph_summary(
    revision: Optional[str] = Query(None),
    repo_data: tuple[User, Organization, Repository] = Depends(get_authorized_repo),
    db: Session = Depends(get_db),
):
    """Returns repository knowledge graph metrics and structural summary from FalkorDB."""
    user, org, repo = repo_data
    rev = revision or repo.indexed_commit_sha or repo.default_branch or "HEAD"

    graph = FalkorRepositoryGraph(tenant_slug=org.slug)
    summary = graph.get_graph_summary(repo=repo.full_name, revision=rev)

    index_summary = None
    if repo.index_summary_json:
        try:
            index_summary = json.loads(repo.index_summary_json)
        except Exception:
            index_summary = None

    return {
        "repository": repo.full_name,
        "tenant_slug": org.slug,
        "graph_id": graph.graph_id,
        "indexing_status": repo.indexing_status or "not_indexed",
        "indexed_commit_sha": repo.indexed_commit_sha,
        "indexed_at": repo.indexed_at.isoformat() if repo.indexed_at else None,
        "graph_summary": summary,
        "index_summary": index_summary,
    }
