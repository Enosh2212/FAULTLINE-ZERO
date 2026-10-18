"""Authenticated workspace read models. No local-demo records enter these responses."""
from __future__ import annotations

import json
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from faultline.auth.dependencies import get_authorized_org, get_authorized_repo, verify_csrf
from faultline.config import get_settings
from faultline.db.models import BackgroundJob, Investigation, PullRequest, Repository, utcnow
from faultline.db.session import get_db
from faultline.github.client import get_github_client
from faultline.graph_engine import FalkorRepositoryGraph
from faultline.queue.job_queue import JobQueue

router = APIRouter(prefix="/api/v1/workspace", tags=["Workspace"])


def parsed(value, fallback=None):
    try:
        return json.loads(value) if value else fallback
    except (ValueError, TypeError):
        return fallback


def date(value):
    return value.isoformat() if value else None


def live_github():
    client = get_github_client()
    if client.mock_mode:
        raise HTTPException(503, "GitHub App credentials are not configured. Repository operations are unavailable.")
    return client


def capabilities():
    settings = get_settings()
    client = get_github_client()
    return {
        "github_app_configured": not client.mock_mode,
        "github_authorization_configured": bool(settings.github_client_id and settings.github_client_secret),
        "webhook_configured": bool(settings.github_webhook_secret and settings.github_webhook_secret != "dev-webhook-secret"),
        "public_installation_verified": False,
        "indexing_limits": "500 files, 512 KB per blob, 8 MB total text. Static Python parsing is supported; other files may be unresolved.",
        "analysis": "Read-only Python AST and dependency analysis; external repository code is never executed.",
        "limitations": "Execution verification requires an applicable, explicitly verified invariant. Other languages and dynamic dependencies may be unresolved.",
    }


def repo_record(repo):
    index = parsed(repo.index_summary_json, {})
    installation = repo.installation
    if not installation or installation.is_suspended:
        monitoring = "Needs reauthorization"
    elif not repo.is_active:
        monitoring = "Paused"
    elif repo.indexing_status in {"indexing", "queued"}:
        monitoring = "Indexing"
    elif repo.indexing_status == "indexed":
        monitoring = "Ready for webhooks"  # Readiness, not proof that GitHub is delivering events.
    else:
        monitoring = "Setup incomplete"
    return dict(id=repo.id, full_name=repo.full_name, default_branch=repo.default_branch,
                is_private=repo.is_private, is_active=repo.is_active,
                installation_id=repo.installation_id, account=installation.account_login if installation else None,
                indexing_status=repo.indexing_status, indexed_commit_sha=repo.indexed_commit_sha,
                indexed_at=date(repo.indexed_at), index_summary=index,
                languages=index.get("languages"), monitoring=monitoring)


def investigation_record(inv):
    pr = inv.pull_request
    return dict(id=inv.id, repository_id=inv.repository_id, repository=inv.repository.full_name,
                pr_id=inv.pull_request_id, pr_number=pr.github_pr_number if pr else None,
                title=pr.title if pr else "Commit investigation", commit_sha=inv.commit_sha,
                base_sha=pr.base_sha if pr else None, head_branch=pr.head_branch if pr else None,
                status=inv.status, verdict=inv.verdict, confidence=inv.confidence,
                summary=inv.summary, created_at=date(inv.created_at), completed_at=date(inv.completed_at),
                check_run_id=inv.check_run_id, superseded=bool(pr and pr.head_sha != inv.commit_sha))


@router.get("/overview")
def overview(response: Response, auth=Depends(get_authorized_org), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    _, org, membership = auth
    repos = db.query(Repository).filter_by(organization_id=org.id, is_active=True).order_by(Repository.full_name).limit(500).all()
    invs = db.query(Investigation).join(Repository).filter(Repository.organization_id == org.id)
    jobs = db.query(BackgroundJob).filter_by(organization_id=org.id)
    return dict(workspace={"id": org.id, "name": org.name, "role": membership.role},
                metrics={"repositories": db.query(Repository).filter_by(organization_id=org.id, is_active=True).count(),
                         "prs_analyzed": invs.filter(Investigation.status == "completed", Investigation.pull_request_id.is_not(None)).with_entities(Investigation.pull_request_id).distinct().count(),
                         "findings": invs.filter(Investigation.status == "completed", Investigation.verdict == "REPRODUCED").count(),
                         "inconclusive": invs.filter(Investigation.status == "completed", Investigation.verdict == "INCONCLUSIVE").count()},
                repositories=[repo_record(r) for r in repos],
                recent_investigations=[investigation_record(i) for i in invs.order_by(Investigation.created_at.desc()).limit(8)],
                active_jobs=jobs.filter(BackgroundJob.status.in_(["queued", "running"])).count(), capabilities=capabilities())


@router.get("/pull-requests")
def pull_requests(repo_id: str | None = None, auth=Depends(get_authorized_org), db: Session = Depends(get_db)):
    query = db.query(PullRequest).join(Repository).filter(Repository.organization_id == auth[1].id)
    if repo_id:
        query = query.filter(PullRequest.repository_id == repo_id)
    result = []
    for pr in query.order_by(PullRequest.updated_at.desc()).limit(200):
        latest = db.query(Investigation).filter_by(pull_request_id=pr.id).order_by(Investigation.created_at.desc()).first()
        result.append(dict(id=pr.id, repository_id=pr.repository_id, repository=pr.repository.full_name,
                           number=pr.github_pr_number, title=pr.title, state=pr.state, head_sha=pr.head_sha,
                           head_branch=pr.head_branch, base_sha=pr.base_sha, author=pr.author_login,
                           updated_at=date(pr.updated_at), investigation=investigation_record(latest) if latest else None))
    return {"items": result, "limit": 200}


@router.get("/investigations")
def investigations(repo_id: str | None = None, auth=Depends(get_authorized_org), db: Session = Depends(get_db)):
    query = db.query(Investigation).join(Repository).filter(Repository.organization_id == auth[1].id)
    if repo_id:
        query = query.filter(Investigation.repository_id == repo_id)
    return {"items": [investigation_record(i) for i in query.order_by(Investigation.created_at.desc()).limit(200)], "limit": 200}


@router.get("/investigations/{investigation_id}")
def investigation_detail(investigation_id: str, auth=Depends(get_authorized_org), db: Session = Depends(get_db)):
    inv = db.query(Investigation).join(Repository).filter(Investigation.id == investigation_id, Repository.organization_id == auth[1].id).first()
    if not inv:
        raise HTTPException(404, "Investigation not found")
    report = parsed(inv.report_json, {})
    # Deliberately expose known evidence fields, never arbitrary stored job payloads or errors.
    fields = ("changed_files", "verification_method", "invariant_id", "affected_services", "is_docs_only", "changed_components", "impacted_callers", "covering_tests", "protecting_invariants")
    record = investigation_record(inv)
    record["evidence"] = {k: report[k] for k in fields if k in report}
    record["graph"] = parsed(inv.evidence_graph_json, {"nodes": [], "edges": []})
    record["scope"] = f"{len(report.get('changed_components') or [])} static symbol comparisons recorded. No arbitrary external repository code was executed."
    record["unverified_scope"] = "Runtime behavior and dependencies outside the recorded analysis are unverified. CLEAN applies only to the reported scope."
    record["activity"] = [{"label": "Investigation recorded", "at": date(inv.created_at)}]
    if inv.completed_at:
        record["activity"].append({"label": "Analysis completed" if inv.status == "completed" else inv.status, "at": date(inv.completed_at)})
    record["check_url"] = f"https://github.com/{inv.repository.full_name}/runs/{inv.check_run_id}" if inv.check_run_id else None
    record["check_note"] = "Check ID recorded; publication outcome is not separately persisted." if inv.check_run_id else "No GitHub Check ID recorded."
    return record


@router.get("/activity")
def activity(auth=Depends(get_authorized_org), db: Session = Depends(get_db)):
    repos = {r.id: r.full_name for r in db.query(Repository).filter_by(organization_id=auth[1].id)}
    items = []
    for j in db.query(BackgroundJob).filter_by(organization_id=auth[1].id).order_by(BackgroundJob.updated_at.desc()).limit(200):
        items.append(dict(id=j.id, type=j.job_type, repository_id=j.repository_id, repository=repos.get(j.repository_id),
                          status=j.status, attempts=j.attempts, max_attempts=j.max_attempts,
                          created_at=date(j.created_at), updated_at=date(j.updated_at),
                          error="The last attempt failed. Check access and service configuration, then retry." if j.error_message and j.status != "cancelled" else None,
                          retryable=j.status in {"failed", "queued"} and j.attempts > 0 and j.attempts < j.max_attempts and j.job_type == "index_repository"))
    return {"items": items, "limit": 200}


@router.post("/activity/{job_id}/retry", dependencies=[Depends(verify_csrf)])
def retry_job(job_id: str, tasks: BackgroundTasks, auth=Depends(get_authorized_org), db: Session = Depends(get_db)):
    if auth[2].role not in {"owner", "admin"}:
        raise HTTPException(403, "Workspace admin access required")
    live_github()
    job = db.query(BackgroundJob).filter_by(id=job_id, organization_id=auth[1].id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.job_type != "index_repository" or job.status not in {"failed", "queued"} or job.attempts == 0 or job.attempts >= job.max_attempts:
        raise HTTPException(409, "This job cannot be retried. Start a fresh repository index if needed.")
    repo = db.query(Repository).filter_by(id=job.repository_id, organization_id=auth[1].id).first()
    if not repo or not repo.installation or repo.installation.is_suspended or not repo.is_active:
        raise HTTPException(409, "Repository access needs attention before retry")
    job.status, job.error_message, job.updated_at = "queued", None, utcnow()
    repo.indexing_status = "queued"
    db.commit()
    tasks.add_task(JobQueue.process_job_now, job.id)
    return {"status": "queued", "job_id": job.id}


@router.get("/repositories/{repo_id}/graph")
def graph_data(focus: str | None = None, q: str = Query("", max_length=120), kind: str = Query("", max_length=30),
               limit: int = Query(100, ge=1, le=150), repo_data=Depends(get_authorized_repo)):
    _, org, repo = repo_data
    revision = repo.indexed_commit_sha
    if not revision:
        raise HTTPException(409, "Index this repository before exploring its dependency graph")
    graph = FalkorRepositoryGraph(tenant_slug=org.slug)
    params = dict(repo=repo.full_name, revision=revision, organization=org.id, needle=q.lower(), kind=kind, limit=limit + 1)
    # Every query scopes both endpoints to organization, repository AND immutable snapshot.
    where = "n.repository=$repo AND n.revision=$revision AND n.tenant_id=$organization"
    try:
        if focus:
            params["focus"] = focus
            rows = graph.read("MATCH (f)-[r]-(n) WHERE f.id=$focus AND f.repository=$repo AND f.revision=$revision AND f.tenant_id=$organization AND " + where + " RETURN DISTINCT n.id,n.name,labels(n)[0],n.path,n.start_line LIMIT $limit", **params)
            rows += graph.read("MATCH (n) WHERE n.id=$focus AND " + where + " RETURN n.id,n.name,labels(n)[0],n.path,n.start_line LIMIT 1", **params)
        else:
            rows = graph.read("MATCH (n) WHERE " + where + " AND ($kind='' OR labels(n)[0]=$kind) AND ($needle='' OR toLower(n.name) CONTAINS $needle) RETURN n.id,n.name,labels(n)[0],n.path,n.start_line ORDER BY n.name LIMIT $limit", **params)
        truncated = len(rows) > limit
        rows = rows[:limit]
        ids = [r[0] for r in rows]
        edges = graph.read("MATCH (a)-[r]->(b) WHERE a.id IN $ids AND b.id IN $ids AND a.repository=$repo AND b.repository=$repo AND a.revision=$revision AND b.revision=$revision AND a.tenant_id=$organization AND b.tenant_id=$organization RETURN a.id,b.id,type(r),r.line LIMIT 401", ids=ids, **params) if ids else []
    except Exception as exc:
        raise HTTPException(503, "Dependency graph is unavailable. Check FalkorDB in service settings.") from exc
    return {"repository": repo.full_name, "revision": revision, "truncated": truncated or len(edges) > 400,
            "limit": limit, "nodes": [dict(id=r[0], label=r[1], type=r[2], path=r[3], line=r[4]) for r in rows],
            "edges": [dict(source=r[0], target=r[1], label=r[2], line=r[3]) for r in edges[:400]],
            "coverage": "Recorded static relationships only; dynamic calls and unresolved imports may be absent."}
