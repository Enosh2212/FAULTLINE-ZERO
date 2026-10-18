"""Comprehensive test suite for FAULTLINE ZERO Phase 3: Graph-Native Repository Intelligence.

Covers:
1. PythonASTExtractor: functions, classes, imports, entry points, assertions, calls.
2. AST Symbol Comparison: IDENTICAL, DOCS_ONLY, SEMANTIC_MODIFIED, ADDED, REMOVED.
3. GitHubRepositoryIndexer: remote tree indexing, limits, language filters.
4. FalkorRepositoryGraph: tenant-isolated Cypher scoping, ID generation, traversal.
5. GitHub API Endpoints: repository indexing (POST) and graph summary inspection (GET).
6. Evidence-backed PR Investigation: honest INCONCLUSIVE verdict for doc-only PRs.
"""
from __future__ import annotations

import ast
import json
import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from faultline.auth.dependencies import get_authorized_repo, verify_csrf
from faultline.ast_engine import PythonASTExtractor, compare_symbol_ast
from faultline.db.models import (
    Base,
    BackgroundJob,
    GitHubInstallation,
    Investigation,
    Membership,
    Organization,
    PullRequest,
    Repository,
    User,
)
from faultline.db.session import get_db
from faultline.github.client import GitHubAppClient
from faultline.github.indexer import GitHubRepositoryIndexer
from faultline.graph_engine import FalkorRepositoryGraph, sanitize_graph_identifier
from faultline.investigator.pr_investigator import (
    format_check_run_markdown,
    handle_index_repository,
    handle_investigate_pr,
)
from faultline.queue.job_queue import JobQueue


@pytest.fixture
def db_session():
    """Provides an isolated in-memory SQLite database session for unit tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    JobQueue.session_factory_override = SessionLocal
    try:
        yield db
    finally:
        db.close()


# ==============================================================================
# 1. AST Extractor Tests
# ==============================================================================

def test_ast_extractor_extracts_symbols_and_metadata():
    source_code = '''"""Sample module docstring."""
import os
import sys
from collections import defaultdict
from .utils import helper

GLOBAL_VAR = 42

class PaymentGateway:
    """Handles payment transactions."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key

    def charge(self, amount: float) -> bool:
        if amount <= 0:
            return False
        return True

def process_order(order_id: str, amount: float) -> bool:
    gateway = PaymentGateway("key_123")
    return gateway.charge(amount)

if __name__ == "__main__":
    process_order("ord_99", 50.0)
'''
    extractor = PythonASTExtractor(source_code, "src/payments/gateway.py")
    result = extractor.extract()

    assert result["path"] == "src/payments/gateway.py"
    assert result["lines"] > 20
    assert result["is_entry_point"] is True

    # Symbols check
    symbols = {s["name"]: s for s in result["symbols"]}
    assert "PaymentGateway" in symbols
    assert symbols["PaymentGateway"]["kind"] == "ClassDef"
    assert "PaymentGateway.charge" in symbols
    assert symbols["PaymentGateway.charge"]["kind"] == "FunctionDef"
    assert "process_order" in symbols

    # Imports check
    imports = result["imports"]
    module_imports = [imp["module"] for imp in imports]
    assert "os" in module_imports
    assert "sys" in module_imports
    assert "collections" in module_imports

    # Calls check
    calls = result["calls"]
    assert any("charge" in c["callee"] or "PaymentGateway" in c["callee"] for c in calls)


def test_ast_extractor_identifies_test_functions_and_assertions():
    source_code = '''
def test_payment_charge_success():
    assert True is True
    assert 1 + 1 == 2

def test_payment_zero_amount():
    assert 0 == 0
'''
    extractor = PythonASTExtractor(source_code, "tests/test_payment.py")
    result = extractor.extract()

    tests = {t["name"]: t for t in result["tests"]}
    assert "test_payment_charge_success" in tests
    assert tests["test_payment_charge_success"]["assertions_count"] == 2
    assert "test_payment_zero_amount" in tests
    assert tests["test_payment_zero_amount"]["assertions_count"] == 1


def test_ast_extractor_handles_syntax_errors_gracefully():
    malformed_code = "def broken_syntax(:\n    return {"
    extractor = PythonASTExtractor(malformed_code, "src/broken.py")
    result = extractor.extract()

    assert result["path"] == "src/broken.py"
    assert result["symbols"] == []
    assert result["imports"] == []
    assert result["calls"] == []


# ==============================================================================
# 2. AST Comparison & Doc-Only Change Detection Tests
# ==============================================================================

def test_ast_comparison_detects_identical_symbols():
    code = "def compute(x):\n    return x * 2\n"
    res = compare_symbol_ast(code, code, "compute")
    assert res["status"] == "IDENTICAL"
    assert res["is_semantic"] is False


def test_ast_comparison_detects_docs_and_comments_only_change():
    base_code = """
def build_features(dataframe):
    return dataframe.copy()
"""
    head_code = """
def build_features(dataframe):
    \"\"\"Constructs high-signal risk indicators from raw account events.\"\"\"
    # Create an isolated copy to prevent in-place mutation of input data
    return dataframe.copy()
"""
    res = compare_symbol_ast(base_code, head_code, "build_features")
    assert res["status"] == "DOCS_ONLY"
    assert res["is_semantic"] is False
    assert "docstring" in res["details"].lower() or "identical" in res["details"].lower()


def test_ast_comparison_detects_semantic_modifications():
    base_code = """
def calculate_discount(price, tier):
    if tier == 'VIP':
        return price * 0.8
    return price
"""
    head_code = """
def calculate_discount(price, tier):
    if tier == 'VIP':
        return price * 0.7  # Changed discount from 20% to 30%
    return price
"""
    res = compare_symbol_ast(base_code, head_code, "calculate_discount")
    assert res["status"] == "SEMANTIC_MODIFIED"
    assert res["is_semantic"] is True
    assert "modified" in res["details"].lower()


def test_ast_comparison_handles_added_and_removed_symbols():
    code_a = "def original_func():\n    pass\n"
    code_b = "def newly_added_func():\n    pass\n"

    # Added symbol
    res_added = compare_symbol_ast(code_a, code_b, "newly_added_func")
    assert res_added["status"] == "ADDED"
    assert res_added["is_semantic"] is True

    # Removed symbol
    res_removed = compare_symbol_ast(code_a, code_b, "original_func")
    assert res_removed["status"] == "REMOVED"
    assert res_removed["is_semantic"] is True


# ==============================================================================
# 3. GitHub Indexer Tests (Mock Mode)
# ==============================================================================

def test_github_indexer_indexes_repository_tree():
    mock_tree = [
        {"path": "src/features/build_features.py", "type": "blob", "sha": "blob_feat_1", "size": 300},
        {"path": "src/models/train.py", "type": "blob", "sha": "blob_train_1", "size": 450},
        {"path": "tests/test_features.py", "type": "blob", "sha": "blob_test_1", "size": 250},
        {"path": "README.md", "type": "blob", "sha": "blob_readme_1", "size": 1200},
        {"path": "static/app.js", "type": "blob", "sha": "blob_js_1", "size": 500},
    ]

    blobs = {
        "src/features/build_features.py": "def build_features(df):\n    return df.copy()\n",
        "src/models/train.py": "from src.features.build_features import build_features\ndef train():\n    build_features(None)\n",
        "tests/test_features.py": "def test_features():\n    assert True\n",
        "blob_feat_1": "def build_features(df):\n    return df.copy()\n",
        "blob_train_1": "from src.features.build_features import build_features\ndef train():\n    build_features(None)\n",
        "blob_test_1": "def test_features():\n    assert True\n",
    }

    mock_client = MagicMock()
    mock_client.get_repository_tree.return_value = mock_tree
    mock_client.get_file_content.side_effect = lambda **kwargs: blobs.get(kwargs.get("path") or kwargs.get("ref"), "")
    mock_client.get_blob.side_effect = lambda **kwargs: blobs.get(kwargs.get("blob_sha"), "")

    with patch("faultline.github.indexer.get_github_client", return_value=mock_client):
        indexer = GitHubRepositoryIndexer(
            installation_id=172633902,
            full_name="Enosh2212/risklens-ai",
        )
        index = indexer.index("main")

        assert len(index["files"]) == 4  # 3 Python source files + 1 README.md
        python_files = [f for f in index["files"] if f["language"] == "Python"]
        assert len(python_files) == 3
        assert "Python" in index["languages"] or "python" in [l.lower() for l in index["languages"]]
        assert index["metrics"]["indexed_files"] == 4


# ==============================================================================
# 4. FalkorDB Graph Engine & Tenant Isolation Tests
# ==============================================================================

def test_falkor_graph_tenant_isolation_and_identifiers():
    slug_1 = sanitize_graph_identifier("Acme Corp - Production")
    assert slug_1 == "acme_corp___production"

    graph_acme = FalkorRepositoryGraph(tenant_slug="acme-corp")
    graph_beta = FalkorRepositoryGraph(tenant_slug="beta-inc")

    assert graph_acme.graph_name == "fz_tenant_acme_corp"
    assert graph_beta.graph_name == "fz_tenant_beta_inc"

    # Scoped IDs must prevent symbol leakage
    id_1 = graph_acme.scoped_id("owner/repo", "rev1", "Function", "process_order")
    id_2 = graph_beta.scoped_id("owner/repo", "rev1", "Function", "process_order")
    assert id_1 != id_2
    assert "acme_corp" in id_1
    assert "beta_inc" in id_2


def test_falkor_graph_traversal_returns_empty_when_unavailable():
    graph = FalkorRepositoryGraph(tenant_slug="test-tenant")
    # Simulate unavailable graph
    with patch.object(graph, "read", side_effect=Exception("FalkorDB connection refused")):
        callers = graph.find_impacted_callers("owner/repo", "sha1", ["compute"])
        assert callers == []

        tests = graph.find_covering_tests("owner/repo", "sha1", ["compute"])
        assert tests == []

        invs = graph.find_protecting_invariants("owner/repo", "sha1", ["compute"])
        assert invs == []


# ==============================================================================
# 5. Background Job & Router Endpoints Tests
# ==============================================================================

def test_router_index_repository_endpoint(db_session, monkeypatch):
    """Verifies POST /api/v1/github/repositories/{repo_id}/index enqueues indexing."""
    from faultline.api import app

    org = Organization(id="org-test-idx", name="Index Org", slug="index-org")
    user = User(id="user-idx", firebase_uid="fb-idx", email="dev@index.org", display_name="Indexer Dev")
    mem = Membership(id="mem-idx", user_id=user.id, organization_id=org.id, role="owner")
    db_session.add_all([org, user, mem])
    db_session.flush()

    inst = GitHubInstallation(id=889900, organization_id=org.id, account_login="org-index")
    db_session.add(inst)
    db_session.flush()

    repo = Repository(
        id="repo-idx-1",
        organization_id=org.id,
        installation_id=inst.id,
        github_repo_id=987654,
        full_name="index-org/app",
        is_private=True,
    )
    db_session.add(repo)
    db_session.commit()

    app.dependency_overrides[get_authorized_repo] = lambda: (user, org, repo)
    app.dependency_overrides[verify_csrf] = lambda: None
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)
        res = client.post(f"/api/v1/github/repositories/{repo.id}/index", json={"revision": "feat/ai"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "indexing_queued"
        assert data["repository"] == "index-org/app"
        assert data["revision"] == "feat/ai"

        # Verify background job enqueued
        job = db_session.query(BackgroundJob).filter_by(repository_id=repo.id).first()
        assert job is not None
        assert job.job_type == "index_repository"
    finally:
        app.dependency_overrides.pop(get_authorized_repo, None)
        app.dependency_overrides.pop(verify_csrf, None)
        app.dependency_overrides.pop(get_db, None)


def test_router_get_repository_graph_summary(db_session, monkeypatch):
    """Verifies GET /api/v1/github/repositories/{repo_id}/graph returns structural metrics."""
    from faultline.api import app

    org = Organization(id="org-graph-1", name="Graph Org", slug="graph-org")
    user = User(id="user-graph-1", firebase_uid="fb-graph-1", email="graph@test.org", display_name="Graph Engineer")
    mem = Membership(id="mem-graph-1", user_id=user.id, organization_id=org.id, role="admin")
    db_session.add_all([org, user, mem])
    db_session.flush()

    inst = GitHubInstallation(id=778899, organization_id=org.id, account_login="graph-org")
    db_session.add(inst)
    db_session.flush()

    repo = Repository(
        id="repo-graph-test-1",
        organization_id=org.id,
        installation_id=inst.id,
        github_repo_id=11223344,
        full_name="graph-org/repo",
        is_private=False,
        indexing_status="indexed",
        indexed_commit_sha="04825fb8236ef9bec5a4212eb352f3f7fc082d22",
        index_summary_json=json.dumps({
            "indexed_files": 12,
            "languages": ["python"],
            "node_count": 48,
            "edge_count": 72,
        }),
    )
    db_session.add(repo)
    db_session.commit()

    app.dependency_overrides[get_authorized_repo] = lambda: (user, org, repo)
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        client = TestClient(app)
        res = client.get(f"/api/v1/github/repositories/{repo.id}/graph")
        assert res.status_code == 200
        data = res.json()
        assert data["repository"] == "graph-org/repo"
        assert data["tenant_slug"] == "graph-org"
        assert data["indexing_status"] == "indexed"
        assert data["index_summary"]["indexed_files"] == 12
        assert data["index_summary"]["node_count"] == 48
    finally:
        app.dependency_overrides.pop(get_authorized_repo, None)
        app.dependency_overrides.pop(get_db, None)


# ==============================================================================
# 6. Live RiskLens AI Scenario: Documentation-Only PR Handling
# ==============================================================================

def test_risklens_doc_only_pr_investigation_verdict_and_markdown(db_session, monkeypatch):
    """
    Simulates the exact RiskLens AI PR #1 scenario:
    - User added docstring and comment to `build_features` in `src/features/build_features.py`
    - AST engine verifies status is DOCS_ONLY and is_semantic is False
    - Downstream blast radius is zero
    - Investigator produces honest INCONCLUSIVE verdict with neutral conclusion
    """
    mock_gh = GitHubAppClient(mock_mode=True)

    base_content = "def build_features(dataframe):\n    return dataframe.copy()\n"
    head_content = '''def build_features(dataframe):
    """Constructs high-signal risk indicators from raw account events."""
    # Create an isolated copy to prevent in-place mutation of input data
    return dataframe.copy()
'''

    # Setup mock file retrieval
    def mock_get_content(installation_id, owner, repo, path, ref=""):
        if "build_features" in path:
            return head_content if "head" in ref or "04825fb" in ref else base_content
        return ""

    def mock_get_pr_files(installation_id, owner, repo, pr_number):
        return [{
            "filename": "src/features/build_features.py",
            "status": "modified",
            "additions": 4,
            "deletions": 0,
            "changes": 4,
            "patch": "+    \"\"\"Constructs high-signal risk indicators from raw account events.\"\"\"\n+    # Create an isolated copy",
        }]

    monkeypatch.setattr(mock_gh, "get_file_content", mock_get_content)
    monkeypatch.setattr(mock_gh, "get_pr_files", mock_get_pr_files)
    monkeypatch.setattr("faultline.github.client._global_github_client", mock_gh)

    org = Organization(id="org-rl-live", name="RiskLens AI", slug="risklens-ai")
    inst = GitHubInstallation(id=172633902, organization_id=org.id, account_login="Enosh2212")
    repo = Repository(
        id="repo-rl-live",
        organization_id=org.id,
        installation_id=inst.id,
        github_repo_id=1295366718,
        full_name="Enosh2212/risklens-ai",
        is_private=False,
    )
    pr = PullRequest(
        id="pr-rl-live-1",
        repository_id=repo.id,
        github_pr_number=1,
        title="test: verify FAULTLINE ZERO live PR investigation",
        head_sha="04825fb8236ef9bec5a4212eb352f3f7fc082d22",
        base_sha="main",
        state="open",
    )
    db_session.add_all([org, inst, repo, pr])
    db_session.commit()

    job = BackgroundJob(
        id="job-rl-live-1",
        organization_id=org.id,
        repository_id=repo.id,
        pull_request_id=pr.id,
        job_type="investigate_pr",
        idempotency_key="job-rl-live-1",
        status="running",
        payload_json=json.dumps({
            "repository_id": repo.id,
            "pull_request_id": pr.id,
            "full_name": repo.full_name,
            "head_sha": pr.head_sha,
            "base_sha": pr.base_sha,
            "pr_number": pr.github_pr_number,
            "check_run_id": 117656519419,
            "installation_id": inst.id,
        }),
    )
    db_session.add(job)
    db_session.commit()

    # Execute investigation
    handle_investigate_pr(job, db_session)

    # Validate investigation outcome
    inv = db_session.query(Investigation).filter_by(repository_id=repo.id, commit_sha=pr.head_sha).first()
    assert inv is not None
    assert inv.verdict == "INCONCLUSIVE"
    assert inv.status == "completed"

    report = json.loads(inv.report_json)
    assert report["is_docs_only"] is True
    assert len(report["changed_components"]) == 1
    assert report["changed_components"][0]["status"] == "DOCS_ONLY"
    assert report["changed_components"][0]["is_semantic"] is False

    # Check Markdown formatting honesty
    title, conclusion, text = format_check_run_markdown(
        verdict=inv.verdict,
        pr_number=pr.github_pr_number,
        head_sha=pr.head_sha,
        base_sha=pr.base_sha,
        changed_components=report["changed_components"],
        impacted_callers=[],
        covering_tests=[],
        protecting_invariants=[],
        is_docs_only=report["is_docs_only"],
        repo_full_name=repo.full_name,
    )

    assert conclusion == "neutral"
    assert "Non-Functional / Documentation Only" in title
    assert "Documentation / Non-Semantic" in text
    assert "Changed Components & AST Semantic Classification" in text
    assert "Downstream Blast Radius & Call Graph" in text
    assert "Investigation Findings & Limitations" in text


def test_risklens_actual_change_with_utf8_bom():
    """
    Direct regression test:
    RiskLens AI base file contained a UTF-8 BOM character (\ufeff).
    compare_symbol_ast must strip the BOM and identify that 'build_features'
    is DOCS_ONLY (non-semantic), rather than incorrectly classifying it as ADDED.
    """
    raw_base = (
        '\ufeff"""Placeholder feature engineering module for RiskLens AI."""\n\n\n'
        "def build_features(dataframe):\n"
        '    """Create simple feature engineering placeholders."""\n'
        "    return dataframe.copy()\n"
    )
    raw_head = (
        '"""Placeholder feature engineering module for RiskLens AI."""\n\n\n'
        "def build_features(dataframe):\n"
        '    """Create simple feature engineering placeholders.\n\n'
        "    Ensures input dataframe immutability by creating an isolated copy for downstream transformations.\n"
        '    """\n'
        "    # Create defensive copy of input dataset to prevent upstream mutations\n"
        "    return dataframe.copy()\n"
    )

    res = compare_symbol_ast(raw_base, raw_head, "build_features")
    assert res["status"] == "DOCS_ONLY"
    assert res["is_semantic"] is False
    assert "build_features" in res["details"]
