"""Session-bound GitHub App authorization; redirect IDs are never proof of access."""
from __future__ import annotations

import json
import hmac
from urllib.parse import quote, urlencode
import httpx
from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from faultline.config import get_settings
from faultline.db.models import AuditEvent, GitHubInstallation, Repository, WorkspaceInstallation, utcnow
from faultline.github.client import generate_install_state, get_github_client, verify_install_state

COOKIE = "fz_github_connect"


def configuration():
    settings = get_settings()
    gh = get_github_client()
    if gh.mock_mode or not settings.github_client_id or not settings.github_client_secret:
        raise HTTPException(503, "Secure GitHub onboarding needs GitHub App credentials and its OAuth client ID/secret on the server. Firebase GitHub sign-in does not grant repository access.")
    return settings, gh


def admin(auth):
    if auth[2].role not in {"owner", "admin"}:
        raise HTTPException(403, "A workspace owner or admin must connect repositories")


def callback_url(request, settings):
    origin = str(request.base_url).rstrip("/")
    if origin not in settings.allowed_origins:
        raise HTTPException(400, "This application origin is not configured for GitHub authorization")
    return origin + "/api/v1/github/oauth/callback"


def headers(token):
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def api_get(client, path, token):
    response = client.get("https://api.github.com" + path, headers=headers(token))
    response.raise_for_status()
    return response.json()


def pages(client, path, token, key):
    result = []
    for page in range(1, 11):
        data = api_get(client, f"{path}?per_page=100&page={page}", token)
        batch = data.get(key, [])
        result.extend(batch)
        if len(batch) < 100:
            return result
    raise HTTPException(409, "This installation exceeds the current 1,000-item onboarding limit. Ask an administrator to narrow repository access.")


def put_cookie(response, state, settings):
    response.set_cookie(COOKIE, state, httponly=True, secure=settings.session_cookie_secure, samesite="lax", max_age=1800, path="/api/v1/github")
    response.headers["Cache-Control"] = "no-store"
    return response


def validate_state(request, state, auth):
    admin(auth)
    cookie = request.cookies.get(COOKIE, "")
    if not state or not cookie or not hmac.compare_digest(cookie, state):
        raise HTTPException(400, "GitHub connection expired or did not start in this browser. Start again from Repositories.")
    try:
        payload = verify_install_state(state)
    except Exception as exc:
        raise HTTPException(400, "Invalid or expired GitHub connection state") from exc
    if payload.get("user_id") != auth[0].id or payload.get("org_id") != auth[1].id:
        raise HTTPException(403, "GitHub connection does not belong to the current workspace session")
    return payload


def install_url(request, response, auth, flow="install", prev_repo_ids=None):
    admin(auth)
    settings, gh = configuration()
    try:
        with httpx.Client(timeout=15) as client:
            app = api_get(client, "/app", gh.generate_app_jwt())
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "GitHub App could not be verified. Check its server configuration.") from exc
    state = generate_install_state(auth[1].id, auth[0].id, flow=flow, prev_repo_ids=prev_repo_ids)
    put_cookie(response, state, settings)
    return {"url": f"https://github.com/apps/{app['slug']}/installations/new?" + urlencode({"state": state}), "state": state}


def authorize(request, auth, flow="install", prev_repo_ids=None):
    admin(auth)
    settings, _ = configuration()
    state = generate_install_state(auth[1].id, auth[0].id, flow=flow, prev_repo_ids=prev_repo_ids)
    url = "https://github.com/login/oauth/authorize?" + urlencode({"client_id": settings.github_client_id, "redirect_uri": callback_url(request, settings), "state": state})
    return put_cookie(RedirectResponse(url, status_code=303), state, settings)


def configure_url(request, response, auth, db):
    """Generates the URL to open GitHub's native installation settings to grant access to more repositories."""
    admin(auth)
    settings, gh = configuration()
    user, org, _ = auth

    ws_inst = db.query(WorkspaceInstallation).filter_by(organization_id=org.id).first()
    inst = db.get(GitHubInstallation, ws_inst.installation_id) if ws_inst else None
    if not inst:
        inst = db.query(GitHubInstallation).filter_by(organization_id=org.id).first()

    active_repos = db.query(Repository).filter_by(organization_id=org.id, is_active=True).all()
    prev_repo_ids = [r.github_repo_id for r in active_repos]

    if not inst:
        return install_url(request, response, auth, flow="install", prev_repo_ids=prev_repo_ids)

    account_login = inst.account_login or ""
    if inst.account_type == "Organization" and account_login:
        target_url = f"https://github.com/organizations/{account_login}/settings/installations/{inst.id}"
    else:
        target_url = f"https://github.com/settings/installations/{inst.id}"

    state = generate_install_state(org.id, user.id, flow="add-access", prev_repo_ids=prev_repo_ids)
    put_cookie(response, state, settings)
    return {"url": target_url, "state": state}


def after_install(request, state, auth):
    error = request.query_params.get("error")
    if error:
        return RedirectResponse("/workspace#workspace/repositories?notice=" + quote("GitHub App installation was cancelled. You can connect repositories at any time."), status_code=303)

    payload = validate_state(request, state, auth)
    flow = payload.get("flow", "install")
    prev_repo_ids = payload.get("prev_repo_ids", [])
    return authorize(request, auth, flow=flow, prev_repo_ids=prev_repo_ids)


def oauth_callback(request, code, state, auth, db, tasks=None):
    error = request.query_params.get("error")
    if error:
        desc = request.query_params.get("error_description", "GitHub authorization was declined.")
        res = RedirectResponse("/workspace#workspace/repositories?notice=" + quote(f"GitHub connection was not completed: {desc}"), status_code=303)
        res.delete_cookie(COOKIE, path="/api/v1/github")
        return res

    payload = validate_state(request, state, auth)
    flow = payload.get("flow", "install")
    prev_repo_ids = set(payload.get("prev_repo_ids", []))
    settings, gh = configuration()

    try:
        with httpx.Client(timeout=20) as client:
            response = client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                    "redirect_uri": callback_url(request, settings),
                },
            )
            response.raise_for_status()
            token = response.json().get("access_token")
            if not token:
                raise HTTPException(403, "GitHub authorization was declined or expired. Start again.")

            installations = pages(client, "/user/installations", token, "installations")
            matching_insts = [
                inst for inst in installations
                if int(inst.get("app_id", 0)) == int(gh.app_id) and not inst.get("suspended_at")
            ]

            # If user has not installed the App, redirect directly to GitHub App installation flow
            if not matching_insts:
                app_info = api_get(client, "/app", gh.generate_app_jwt())
                new_state = generate_install_state(auth[1].id, auth[0].id, flow="install")
                redirect_res = RedirectResponse(
                    f"https://github.com/apps/{app_info['slug']}/installations/new?" + urlencode({"state": new_state}),
                    status_code=303,
                )
                put_cookie(redirect_res, new_state, settings)
                return redirect_res

            verified = []
            for installation in matching_insts:
                repos = pages(client, f"/user/installations/{installation['id']}/repositories", token, "repositories")
                admin_repos = [r for r in repos if r.get("permissions", {}).get("admin") is True]
                if admin_repos:
                    verified.append((installation, admin_repos))

        if not verified:
            res = RedirectResponse("/workspace#workspace/repositories?notice=" + quote("No repositories found where you have admin permissions. Grant repository access in GitHub."), status_code=303)
            res.delete_cookie(COOKIE, path="/api/v1/github")
            return res

        total_imported = []
        for data, repos in verified:
            inst = db.get(GitHubInstallation, data["id"])
            if not inst:
                inst = GitHubInstallation(
                    id=data["id"],
                    organization_id=auth[1].id,
                    account_login=data["account"]["login"],
                    account_type=data["account"]["type"],
                )
                db.add(inst)
                db.flush()
            inst.is_suspended = False

            repo_summaries = [
                {
                    "id": r["id"],
                    "full_name": r["full_name"],
                    "private": r.get("private", True),
                    "default_branch": r.get("default_branch", "main"),
                }
                for r in repos
            ]

            ws_inst = db.query(WorkspaceInstallation).filter_by(
                organization_id=auth[1].id, installation_id=data["id"]
            ).first()
            if not ws_inst:
                ws_inst = WorkspaceInstallation(
                    organization_id=auth[1].id,
                    installation_id=data["id"],
                    authorized_by_user_id=auth[0].id,
                    authorized_repositories_json=json.dumps(repo_summaries),
                )
                db.add(ws_inst)
            else:
                ws_inst.authorized_by_user_id = auth[0].id
                ws_inst.authorized_repositories_json = json.dumps(repo_summaries)
                ws_inst.updated_at = utcnow()

            # Determine repositories to automatically import
            if flow == "add-access":
                target_repos = [r for r in repos if r["id"] not in prev_repo_ids]
            elif flow in {"install", "authorize"}:
                target_repos = repos
            else:
                target_repos = []

            for r in target_repos:
                existing_repo = db.query(Repository).filter_by(
                    organization_id=auth[1].id, github_repo_id=r["id"]
                ).first()
                if not existing_repo:
                    repo_obj = Repository(
                        organization_id=auth[1].id,
                        installation_id=inst.id,
                        github_repo_id=r["id"],
                        full_name=r["full_name"],
                        default_branch=r.get("default_branch", "main"),
                        is_private=r.get("private", True),
                        is_active=True,
                        indexing_status="queued",
                    )
                    db.add(repo_obj)
                    db.flush()
                else:
                    repo_obj = existing_repo
                    repo_obj.is_active = True
                    repo_obj.installation_id = inst.id
                    repo_obj.full_name = r["full_name"]
                    repo_obj.is_private = r.get("private", True)
                    repo_obj.default_branch = r.get("default_branch", "main")
                    db.flush()

                total_imported.append(repo_obj)

                try:
                    import time
                    from faultline.queue.job_queue import JobQueue
                    revision = repo_obj.default_branch or "HEAD"
                    window_bucket = int(time.time() // 30)
                    idempotency_key = f"index:{repo_obj.id}:{revision}:{window_bucket}"
                    job = JobQueue.enqueue(
                        db=db,
                        organization_id=auth[1].id,
                        job_type="index_repository",
                        idempotency_key=idempotency_key,
                        payload={"repository_id": repo_obj.id, "revision": revision},
                        repository_id=repo_obj.id,
                    )
                    if job.status == "queued" and tasks:
                        tasks.add_task(JobQueue.process_job_now, job.id)
                except Exception:
                    pass

            db.add(
                AuditEvent(
                    organization_id=auth[1].id,
                    user_id=auth[0].id,
                    action="github_app.authorized",
                    resource_type="GitHubInstallation",
                    resource_id=str(inst.id),
                )
            )

        db.commit()

        if total_imported:
            result = RedirectResponse(
                f"/workspace#workspace/repositories?imported={len(total_imported)}",
                status_code=303,
            )
        else:
            result = RedirectResponse(
                "/workspace#workspace/repositories?notice=" + quote("GitHub authorization refreshed. Your repositories are up to date."),
                status_code=303,
            )

    except Exception as exc:
        db.rollback()
        error_msg = getattr(exc, "detail", str(exc))
        result = RedirectResponse(
            "/workspace#workspace/repositories?error=" + quote(str(error_msg)),
            status_code=303,
        )

    result.delete_cookie(COOKIE, path="/api/v1/github")
    result.headers["Cache-Control"] = "no-store"
    return result
