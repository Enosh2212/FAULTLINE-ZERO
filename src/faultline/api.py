"""HTTP entry point and static zero-build UI."""
from __future__ import annotations
import hmac
import logging
import time
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict

from faultline.git_demo import create_demo, repo_path, inspect_change, TITLES
from faultline.tool_agent import ToolInvestigator

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from faultline.agent import InvestigationAgent
from faultline.auth.router import router as auth_router
from faultline.config import get_settings
from faultline.db.session import get_session_factory, init_db, seed_default_tenant, get_db
from sqlalchemy.orm import Session
from faultline.auth.dependencies import get_current_user, verify_csrf
from fastapi.responses import RedirectResponse
from faultline.github.router import router as github_router
from faultline.graph_repository import FalkorGraphRepository, GraphRepository, GraphUnavailable
import faultline.investigator.pr_investigator  # registers background job handler
from faultline.invariant_registry import InvariantReview
from faultline.runner import ScenarioRunner
from faultline.schema import ChangeSummary, GraphSnapshot, Investigation, InvestigationRequest
from faultline.webhooks.github import router as webhook_router

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
settings = get_settings()


@lru_cache(maxsize=1)
def get_repo() -> FalkorGraphRepository:
    return FalkorGraphRepository(get_settings())


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.is_production:
        from faultline.auth.firebase import get_admin_app
        await run_in_threadpool(get_admin_app)
    # Initialize relational schema and seed default tenant
    try:
        await run_in_threadpool(init_db)
        def _init_startup():
            factory = get_session_factory()
            with factory() as s:
                if settings.auto_seed:
                    seed_default_tenant(s)
                from faultline.queue.job_queue import JobQueue
                JobQueue.recover_abandoned_jobs(s)
        await run_in_threadpool(_init_startup)
        logger.info("Database initialized, startup tenant verified, and abandoned jobs recovered")
    except Exception as exc:
        if settings.is_production:
            raise
        logger.warning("Database startup notice: %s", exc)

    await run_in_threadpool(create_demo, repo_path())
    if settings.auto_seed:
        # Docker health dependency ensures graph is up; a few retries tolerate startup races.
        for attempt in range(8):
            try:
                await run_in_threadpool(get_repo().bootstrap)
                logger.info("Graph bootstrap completed")
                break
            except Exception:
                if attempt == 7:
                    logger.exception("Graph bootstrap failed; graph-dependent endpoints will be unavailable")
                else:
                    await __import__("asyncio").sleep(1)
    yield


app = FastAPI(
    title="FAULTLINE ZERO", description="Evidence-first graph-native regression investigation",
    version="0.2.0", lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Organization-Id"],
)

app.include_router(auth_router)
app.include_router(github_router)
app.include_router(webhook_router)
from faultline.workspace import router as workspace_router
app.include_router(workspace_router)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unexpected server error in %s", request.url.path)
        raise
    response.headers["X-Request-ID"] = request.headers.get("X-Request-ID", "")[:64] or __import__("uuid").uuid4().hex
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    logger.info("%s %s -> %s %.1fms", request.method, request.url.path,
                response.status_code, (time.perf_counter() - started) * 1000)
    if request.url.path == "/workspace" or request.url.path.startswith(("/api/v1/auth/", "/api/v1/workspace/", "/api/v1/github/")):
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Vary"] = "Cookie, X-Organization-Id"
    return response


async def authorize(request: Request, db: Session = Depends(get_db),
                    authorization: Annotated[str | None, Header()] = None) -> None:
    if get_settings().is_production:
        user = await run_in_threadpool(get_current_user, request, db)
        verify_csrf(request, user, request.headers.get("X-CSRF-Token"))
        return
    key = get_settings().api_key
    if key and (not authorization or not hmac.compare_digest(authorization, "Bearer " + key)):
        raise HTTPException(status_code=401, detail="Bearer token required")


RepoDep = Annotated[GraphRepository, Depends(get_repo)]
AuthDep = Annotated[None, Depends(authorize)]


@app.exception_handler(GraphUnavailable)
async def graph_unavailable(_request: Request, _exc: GraphUnavailable):
    return JSONResponse(status_code=503, content={"detail": "Graph store unavailable"})


@app.get("/api/v1/health/live")
def live():
    return {"status": "alive", "version": "0.2.0"}


@app.get("/api/v1/health/ready")
async def ready(repo: RepoDep):
    ok = await run_in_threadpool(repo.ready)
    if not ok:
        raise HTTPException(status_code=503, detail="FalkorDB not ready")
    return {"status": "ready", "graph": "FalkorDB"}


@app.get("/api/v1/meta")
def meta(_: AuthDep):
    return {"name": "FAULTLINE ZERO", "track": "Agents That Act on Connected Data",
            "mode": "trusted Git demo + curated legacy", "version": "0.2.0",
            "model_configured": bool(settings.llm_api_key and settings.llm_base_url and settings.llm_model),
            "fly_memory_enabled": settings.fly_memory_enabled}


@app.get("/api/v1/changes", response_model=list[ChangeSummary])
async def changes(repo: RepoDep, _: AuthDep):
    return await run_in_threadpool(repo.changes)


@app.get("/api/v1/graph", response_model=GraphSnapshot)
async def graph(repo: RepoDep, _: AuthDep):
    return await run_in_threadpool(repo.snapshot)


@app.post("/api/v1/investigations", response_model=Investigation, status_code=201)
async def investigate(body: InvestigationRequest, repo: RepoDep, _: AuthDep):
    agent = InvestigationAgent(repo, ScenarioRunner(get_settings().runner_timeout))
    report = await run_in_threadpool(agent.investigate, body.change_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Unknown change identifier")
    return report


@app.get("/api/v1/investigations", response_model=list[Investigation])
async def investigations(repo: RepoDep, _: AuthDep):
    return await run_in_threadpool(repo.recent_reports, 8)


@app.get("/api/v1/investigations/{report_id}", response_model=Investigation)
async def report(report_id: str, repo: RepoDep, _: AuthDep):
    if len(report_id) > 40 or not report_id.startswith("INV-"):
        raise HTTPException(status_code=400, detail="Invalid investigation id")
    item = await run_in_threadpool(repo.report, report_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return item


class GitInvestigationRequest(BaseModel):
    change: Literal["payment", "inventory", "control", "uncovered", "refund"]
    mode: Literal["auto", "deterministic", "model"] = "auto"


@app.get("/api/v1/repositories")
def repositories(_: AuthDep):
    return [{"id": "trusted-commerce", "name": "Synthetic commerce - local Git", "execution": "bundled verified source only", "changes": TITLES}]


@app.get("/api/v1/git/changes/{key}")
async def git_change(key: Literal["payment", "inventory", "control", "uncovered", "refund"], _: AuthDep):
    try:
        return await run_in_threadpool(inspect_change, key)
    except (ValueError, OSError) as exc:
        raise HTTPException(400, "Trusted Git revision verification failed") from exc


@app.get("/api/v1/graph/evidence/{key}")
async def evidence_graph(key: Literal["payment", "inventory", "control", "uncovered", "refund"], repo: RepoDep, _: AuthDep):
    change_id = "GIT-" + key.upper()
    try:
        return await run_in_threadpool(repo.evidence_subgraph, change_id)
    except Exception as exc:
        raise HTTPException(500, f"Failed to retrieve evidence subgraph: {exc}") from exc


@app.post("/api/v1/verify_provider")
async def verify_provider(_: AuthDep):
    """Test live LLM connectivity without exposing credentials."""
    s = get_settings()
    configured = bool(s.llm_api_key and s.llm_base_url and s.llm_model)
    if not configured:
        return {"configured": False, "status": "NOT_CONFIGURED", "detail": "Missing LLM provider credentials in .env"}
    started = time.perf_counter()
    try:
        from faultline.tool_agent import CompatibleModel
        model = CompatibleModel(s)
        # Small non-destructive ping
        res = await run_in_threadpool(model.choose, [{"role": "user", "content": "Ping: select get_git_diff tool"}], 12)
        latency_ms = int((time.perf_counter() - started) * 1000)
        tool_name = res.get("tool_calls", [{}])[0].get("function", {}).get("name")
        return {
            "configured": True,
            "status": "HEALTHY",
            "model": s.llm_model,
            "latency_ms": latency_ms,
            "tool_call_verified": tool_name == "get_git_diff",
            "usage": model.usage
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "configured": True,
            "status": "ERROR",
            "model": s.llm_model,
            "latency_ms": latency_ms,
            "detail": f"{type(exc).__name__}: {str(exc)[:160]}"
        }


@app.post("/api/v1/git/investigations", response_model=Investigation, status_code=201)
async def git_investigate(body: GitInvestigationRequest, repo: RepoDep, _: AuthDep):
    try:
        agent = await run_in_threadpool(ToolInvestigator, repo, body.change, body.mode)
        return await run_in_threadpool(agent.run)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc



# Project context is additive: registered local repository only, no user paths or source execution.
class ContextIndexRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision: Literal['baseline','payment','inventory','control','uncovered','refund'] = 'baseline'


@app.get('/api/v1/context/understanding')
async def project_understanding(repo: RepoDep, _: AuthDep, revision: Literal['baseline','payment','inventory','control','uncovered','refund']='baseline'):
    from faultline.project_context import service_for
    return await run_in_threadpool(service_for(repo).summary,revision)


@app.post('/api/v1/context/index')
async def index_project_context(body: ContextIndexRequest, repo: RepoDep, _: AuthDep):
    from faultline.project_context import service_for
    return await run_in_threadpool(service_for(repo).summary,body.revision)


@app.get('/api/v1/context/change/{key}')
async def changed_project_context(key: Literal['payment','inventory','control','uncovered','refund'], repo: RepoDep, _: AuthDep):
    from faultline.project_context import service_for
    data=await run_in_threadpool(inspect_change,key)
    return await run_in_threadpool(service_for(repo).prepare_change,data)


@app.get('/api/v1/context/source')
async def indexed_context_source(repo: RepoDep, _: AuthDep, path: str, revision: Literal['baseline','payment','inventory','control','uncovered','refund']='baseline'):
    from faultline.project_context import service_for
    view=await run_in_threadpool(service_for(repo).index,revision)
    source=next((f for f in view['index']['files'] if f['path']==path),None)
    if source is None:raise HTTPException(404,'Source is not part of the indexed revision')
    return {'path':path,'revision':view['revision'],'sha256':source['sha256'],'source':source['source'][:20000],'truncated':len(source['source'])>20000,'execution':'never executed by indexing'}


@app.post('/api/v1/context/invariants/{invariant_id}/review')
async def review_context_invariant(invariant_id: str, body: InvariantReview, repo: RepoDep, _: AuthDep,
                                  x_context_maintainer_token: Annotated[str | None, Header()]=None,
                                  revision: Literal['baseline','payment','inventory','control','uncovered','refund']='baseline'):
    import os
    from faultline.project_context import service_for
    expected=os.getenv('FZ_CONTEXT_MAINTAINER_KEY','')
    if not expected:raise HTTPException(503,'Invariant review is disabled; the supported UI is read-only')
    if not x_context_maintainer_token or not hmac.compare_digest(expected,x_context_maintainer_token):raise HTTPException(403,'Authenticated context-maintainer permission required')
    if body.action=='edit' and not body.description:raise HTTPException(422,'Edited description is required')
    service=service_for(repo)
    view=await run_in_threadpool(service.index,revision)
    try:return await run_in_threadpool(service.store.review,'trusted-commerce',view['revision'],invariant_id,body,'authenticated-context-maintainer')
    except ValueError as exc:raise HTTPException(404,str(exc)) from exc


class FlyMemorySearchRequest(BaseModel):
    symbols: list[str] = []
    services: list[str] = []
    invariants: list[str] = []
    diff_text: str = ""
    top_k: int = 5


@app.get("/api/v1/flymemory/incidents")
def get_flymemory_incidents(_: AuthDep):
    from faultline.flymemory.store import get_flymemory_store
    store = get_flymemory_store()
    return [m.to_dict() for m in store.memories.values()]


@app.post("/api/v1/flymemory/search")
async def search_flymemory(body: FlyMemorySearchRequest, repo: RepoDep, _: AuthDep):
    from faultline.flymemory.retriever import MemoryRetriever
    from faultline.flymemory.store import get_flymemory_store
    store = get_flymemory_store()
    retriever = MemoryRetriever(store=store)
    context = {
        "modified_symbols": body.symbols,
        "services": body.services,
        "invariants": body.invariants,
        "diff": body.diff_text,
    }
    results = await run_in_threadpool(retriever.retrieve, "REPO-COMMERCE", context, repo, body.top_k)
    return [r.to_dict() for r in results]


WEB = Path(__file__).resolve().parent / "web"
app.mount("/assets", StaticFiles(directory=WEB), name="assets")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB / "index.html")


@app.get("/login", include_in_schema=False)
@app.get("/register", include_in_schema=False)
def auth_page():
    return FileResponse(WEB / "auth.html", headers={"Cache-Control": "no-store"})


@app.get("/workspace", include_in_schema=False)
def authenticated_workspace(request: Request, db: Session = Depends(get_db)):
    try:
        get_current_user(request, db)
    except HTTPException as exc:
        if exc.status_code == 401:
            return RedirectResponse("/login?next=%2Fworkspace", status_code=303)
        raise
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-store"})
