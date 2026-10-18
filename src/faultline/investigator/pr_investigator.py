"""Graph-native static AST and FalkorDB-guided pre-merge regression investigator.

Analyzes external GitHub PRs using authorized GitHub installation tokens,
constructs version-aware repository property graphs in FalkorDB, traces downstream
call impacts, discovers test coverage, and evaluates business invariant safety.
Never executes arbitrary repository code; purely read-only and static.
"""
from __future__ import annotations

import ast
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from faultline.ast_engine import PythonASTExtractor, compare_symbol_ast
from faultline.config import get_settings
from faultline.db.models import (
    AuditEvent,
    BackgroundJob,
    Investigation,
    PullRequest,
    Repository,
    utcnow,
)
from faultline.github.client import get_github_client
from faultline.github.indexer import GitHubRepositoryIndexer
from faultline.graph_engine import FalkorRepositoryGraph
from faultline.queue.job_queue import register_job_handler

logger = logging.getLogger("faultline.investigator.pr")


def format_check_run_markdown(
    verdict: str,
    pr_number: int,
    head_sha: str,
    invariant_id: str | None = None,
    affected_services: List[str] | None = None,
    summary: str = "",
    cypher_path: str = "",
    *,
    base_sha: str = "",
    changed_components: Optional[List[Dict[str, Any]]] = None,
    impacted_callers: Optional[List[Dict[str, Any]]] = None,
    covering_tests: Optional[List[Dict[str, Any]]] = None,
    protecting_invariants: Optional[List[Dict[str, Any]]] = None,
    is_docs_only: bool = False,
    repo_full_name: str = "",
) -> Tuple[str, str, str]:
    """Formats title, summary, and text for GitHub Checks API with repository intelligence."""
    affected_services = affected_services or []
    changed_components = changed_components or []
    impacted_callers = impacted_callers or []
    covering_tests = covering_tests or []
    protecting_invariants = protecting_invariants or []

    if verdict == "REPRODUCED":
        title = "FAULTLINE ZERO // Pre-Merge Regression Empirically Proven"
        conclusion = "failure"
        text = f"""### FAULTLINE ZERO Pre-Merge Regression Gate

> **Status:** Regression Detected (Blocking Merge)  
> **Target PR:** #{pr_number} (`{head_sha[:8]}`)  
> **Violated Invariant:** `{invariant_id or 'INV-GEN-01'}`  
> **Blast Radius Services:** {', '.join(f'`{s}`' for s in affected_services) if affected_services else '`Core Service`'}

---

#### 1. Invariant Violation Analysis
{summary}

#### 2. FalkorDB Provenance Graph Path
```cypher
MATCH path = (c:Commit {{sha: '{head_sha[:8]}'}})-[:MODIFIES]->(fn:Function)-[:CALLS*1..3]->(inv:Invariant)
RETURN path
```
**Discovered Traversal:** `{cypher_path}`

#### 3. Recommended Remediation
1. Inspect differential idempotency or boundary check in the modified functions.
2. Verify downstream caller preconditions before merging.
3. Re-run pre-merge verification by pushing an updated commit or requesting check re-run.
"""
    elif verdict == "CLEAN":
        title = "FAULTLINE ZERO // Pre-Merge Verification Passed"
        conclusion = "success"
        text = f"""### FAULTLINE ZERO Pre-Merge Verification Passed

> **Status:** Clean Gate (No Invariant Regressions Detected)  
> **Target PR:** #{pr_number} (`{head_sha[:8]}`)  
> **Evaluated Invariants:** Verified against active system invariant specifications

All static AST symbol dependencies, call graphs, and business invariants in FalkorDB evaluated safely.
"""
    else:
        if is_docs_only:
            title = "FAULTLINE ZERO // Non-Functional / Documentation Only Change"
        else:
            title = "FAULTLINE ZERO // Untested Invariant Scope"
        conclusion = "neutral"

        # Format changed components section
        comp_lines = []
        for c in changed_components[:6]:
            status_badge = f"`[{c.get('status', 'MODIFIED')}]`"
            comp_lines.append(f"- {status_badge} `{c.get('path')}` -> `{c.get('name')}` ({c.get('details', '')})")
        comp_md = "\n".join(comp_lines) if comp_lines else "- No specific modified Python symbols detected."

        # Format caller blast radius section
        caller_lines = []
        for cl in impacted_callers[:5]:
            caller_lines.append(f"- Caller `{cl.get('caller_name')}` in `{cl.get('caller_path')}` (Calls `{cl.get('target_name')}`, Depth: {cl.get('depth')})")
        callers_md = "\n".join(caller_lines) if caller_lines else (
            "- No downstream callers discovered within the indexed repository property graph.\n"
            "  *(Note: Static call-graph indexing observes declared module-level references; it does not claim mathematical impossibility of dynamic dispatch or external API consumers.)*"
        )

        # Format tests section
        test_lines = []
        for t in covering_tests[:4]:
            test_lines.append(f"- Test `{t.get('test_name')}` in `{t.get('test_path')}` (Tests `{t.get('tested_symbol')}`)")
        tests_md = "\n".join(test_lines) if test_lines else "None discovered in repository graph."

        # Format invariants section
        inv_lines = []
        for iv in protecting_invariants[:4]:
            inv_lines.append(f"- Invariant `{iv.get('invariant_name')}`: {iv.get('description')}")
        invs_md = "\n".join(inv_lines) if inv_lines else "0 matching business invariants registered in FalkorDB."

        change_type = "Documentation / Non-Semantic (Comments / Docstrings Only)" if is_docs_only else "Static Code Modifications Detected"

        if is_docs_only:
            findings_body = (
                "AST structural verification confirmed that all modifications to identified symbols are strictly non-semantic "
                "(documentation, docstrings, comments, or formatting). Executable AST bytecode logic remains identical between base and head revisions.\n\n"
                "However, because no verified business invariant specifications are registered in FalkorDB for this service path, "
                "FAULTLINE ZERO records an honest **INCONCLUSIVE** audit rather than falsely certifying automated regression immunity."
            )
        else:
            findings_body = (
                f"{summary}\n\n"
                "No matching business invariant coverage exists in the FalkorDB knowledge graph for the symbols or services modified in this Pull Request.\n"
                "Pre-merge gate cannot guarantee regression immunity without verified invariant rules."
            )

        text = f"""### FAULTLINE ZERO Inconclusive Pre-Merge Audit

> **Status:** Inconclusive (Untested Scope Detected)  
> **Target PR:** #{pr_number} (`{head_sha[:8]}`)  
> **Repository:** `{repo_full_name}`  
> **Modification Classification:** {change_type}  

---

#### 1. Changed Components & AST Semantic Classification
{comp_md}

#### 2. Downstream Blast Radius & Call Graph
{callers_md}

#### 3. Test & Invariant Knowledge Graph Coverage
- **Covering Unit Tests:** {tests_md}
- **Verified Business Invariants:** {invs_md}

#### 4. Investigation Findings & Limitations
{findings_body}
"""

    return title, conclusion, text


@register_job_handler("index_repository")
def handle_index_repository(job: BackgroundJob, db: Session) -> None:
    """Indexes an authorized repository's source tree into FalkorDB in the background."""
    payload = json.loads(job.payload_json)
    repo_id = payload["repository_id"]
    revision = payload.get("revision", "HEAD")

    repo = db.query(Repository).filter_by(id=repo_id).first()
    if not repo:
        raise ValueError(f"Repository {repo_id} not found")

    org = repo.organization
    repo.indexing_status = "indexing"
    db.commit()

    try:
        indexer = GitHubRepositoryIndexer(
            installation_id=repo.installation_id,
            full_name=repo.full_name,
        )
        index_data = indexer.index(revision)

        graph = FalkorRepositoryGraph(tenant_slug=org.slug)
        graph_res = graph.build_and_save_snapshot(
            index=index_data,
            organization_id=org.id,
        )

        repo.indexing_status = "indexed"
        repo.indexed_commit_sha = index_data["revision"]
        repo.indexed_at = utcnow()
        repo.index_summary_json = json.dumps({
            "indexed_files": len(index_data["files"]),
            "languages": index_data["languages"],
            "entry_points": index_data["entry_points"],
            "node_count": graph_res["node_count"],
            "edge_count": graph_res["edge_count"],
            "metrics": index_data["metrics"],
        })
        db.commit()
        logger.info("Successfully indexed repository %s at %s", repo.full_name, index_data["revision"][:8])
    except Exception as exc:
        logger.exception("Failed to index repository %s: %s", repo.full_name, exc)
        repo.indexing_status = "failed"
        db.commit()
        raise


@register_job_handler("investigate_pr")
def handle_investigate_pr(job: BackgroundJob, db: Session) -> None:
    """
    Executes a read-only static AST and FalkorDB graph investigation for an external GitHub PR.
    Crucial Security Boundary: Does NOT execute arbitrary code or test scripts on the host.
    """
    payload = json.loads(job.payload_json)
    repo_id = payload["repository_id"]
    pr_id = payload["pull_request_id"]
    full_name = payload["full_name"]
    head_sha = payload["head_sha"]
    base_sha = payload.get("base_sha", "")
    pr_number = payload["pr_number"]
    check_run_id = payload.get("check_run_id")
    installation_id = payload.get("installation_id")

    repo = db.query(Repository).filter_by(id=repo_id).first()
    pr = db.query(PullRequest).filter_by(id=pr_id).first()
    if not repo or not pr:
        raise ValueError(f"Repository or PR not found for job {job.id}")

    # Verify installation status
    if repo.installation and repo.installation.is_suspended:
        logger.warning("Repository %s installation is suspended; aborting investigation", repo.full_name)
        job.status = "cancelled"
        job.error_message = "GitHub installation suspended or uninstalled"
        db.commit()
        return

    # Stale head-SHA matching: If PR head_sha has changed since job was enqueued, abort
    if pr.head_sha != head_sha:
        logger.info(
            "Stale commit detected for PR #%d (job head_sha=%s, current PR head_sha=%s); aborting investigation",
            pr_number, head_sha[:8], pr.head_sha[:8],
        )
        job.status = "cancelled"
        job.error_message = f"Superseded by newer commit {pr.head_sha[:8]}"
        db.commit()
        return

    # Create or update Investigation record
    investigation = (
        db.query(Investigation)
        .filter_by(repository_id=repo.id, commit_sha=head_sha)
        .first()
    )
    if not investigation:
        investigation = Investigation(
            repository_id=repo.id,
            pull_request_id=pr.id,
            commit_sha=head_sha,
            check_run_id=check_run_id,
            status="running",
        )
        db.add(investigation)
    else:
        investigation.status = "running"
        investigation.check_run_id = check_run_id or investigation.check_run_id

    db.commit()

    gh_client = get_github_client()
    owner, repo_name = full_name.split("/", 1) if "/" in full_name else ("", full_name)

    # --- Step 1: Fetch Changed PR Files & Extract AST ---
    changed_files: List[Dict[str, Any]] = []
    if installation_id and owner and repo_name:
        try:
            changed_files = gh_client.get_pr_files(
                installation_id=installation_id,
                owner=owner,
                repo=repo_name,
                pr_number=pr_number,
            )
        except Exception as exc:
            logger.warning("Could not fetch PR files from GitHub: %s", exc)

    changed_filenames = [f.get("filename", "") for f in changed_files if f.get("filename")]
    modified_symbols_info: List[Dict[str, Any]] = []

    for cf in changed_files:
        fn = cf.get("filename", "")
        if fn.endswith(".py"):
            base_content: Optional[str] = None
            head_content: Optional[str] = None

            if installation_id and owner and repo_name:
                try:
                    head_content = gh_client.get_file_content(
                        installation_id=installation_id,
                        owner=owner,
                        repo=repo_name,
                        path=fn,
                        ref=head_sha,
                    )
                except Exception as exc:
                    logger.warning("Could not fetch head content for %s: %s", fn, exc)

                if base_sha:
                    try:
                        base_content = gh_client.get_file_content(
                            installation_id=installation_id,
                            owner=owner,
                            repo=repo_name,
                            path=fn,
                            ref=base_sha,
                        )
                    except Exception as exc:
                        logger.warning("Could not fetch base content for %s: %s", fn, exc)

            if head_content:
                extractor = PythonASTExtractor(head_content, fn)
                ast_data = extractor.extract()
                for sym in ast_data["symbols"]:
                    sym_name = sym["name"]
                    cmp_res = compare_symbol_ast(base_content, head_content, sym_name)
                    modified_symbols_info.append({
                        "path": fn,
                        "name": sym_name,
                        "start": sym.get("start", 1),
                        "end": sym.get("end", 1),
                        "kind": sym.get("kind", "FunctionDef"),
                        "status": cmp_res["status"],
                        "is_semantic": cmp_res["is_semantic"],
                        "details": cmp_res["details"],
                    })

    # Determine whether changes are exclusively comments/documentation
    is_docs_only = False
    if modified_symbols_info:
        is_docs_only = all(s["status"] in {"IDENTICAL", "DOCS_ONLY"} for s in modified_symbols_info)

    modified_symbol_names = [s["name"] for s in modified_symbols_info]
    semantic_symbol_names = [s["name"] for s in modified_symbols_info if s.get("is_semantic")]

    # --- Step 2: Index Head Snapshot & Query FalkorDB Graph ---
    org = repo.organization
    tenant_slug = org.slug if org else "default"
    repo_graph = FalkorRepositoryGraph(tenant_slug=tenant_slug)
    # Auto-index Base Snapshot in FalkorDB if valid commit SHA
    if installation_id and base_sha and len(base_sha) >= 40:
        try:
            indexer = GitHubRepositoryIndexer(installation_id=installation_id, full_name=full_name)
            base_index = indexer.index(base_sha)
            repo_graph.build_and_save_snapshot(index=base_index, organization_id=repo.organization_id)
        except Exception as exc:
            logger.warning("Auto-indexing repository base snapshot had non-fatal warning: %s", exc)

    # Check if head snapshot needs indexing in FalkorDB
    if installation_id:
        try:
            indexer = GitHubRepositoryIndexer(installation_id=installation_id, full_name=full_name)
            head_index = indexer.index(head_sha)
            repo_graph.build_and_save_snapshot(index=head_index, organization_id=repo.organization_id)
            repo.indexing_status = "indexed"
            repo.indexed_commit_sha = head_sha
            repo.indexed_at = utcnow()
            db.commit()
        except Exception as exc:
            logger.warning("Auto-indexing repository head snapshot had non-fatal warning: %s", exc)

    # Graph Traversal: discover impacted callers, covering tests, and protecting invariants
    try:
        impacted_callers = repo_graph.find_impacted_callers(
            repo=full_name,
            revision=head_sha,
            symbol_names=semantic_symbol_names or modified_symbol_names,
            max_depth=3,
        )
        covering_tests = repo_graph.find_covering_tests(
            repo=full_name,
            revision=head_sha,
            symbol_names=modified_symbol_names,
        )
        protecting_invariants = repo_graph.find_protecting_invariants(
            repo=full_name,
            revision=head_sha,
            symbol_names=modified_symbol_names,
        )
    except Exception as exc:
        logger.warning("FalkorDB graph traversal had non-fatal warning: %s", exc)
        impacted_callers = []
        covering_tests = []
        protecting_invariants = []

    # External repositories have no approved execution verifier in this pipeline.
    # Static matches, names and PR titles are never proof of a reproduced regression.
    verdict, confidence = "INCONCLUSIVE", "LOW"
    invariant_id = None
    affected_services = []
    if not modified_symbols_info:
        summary = "No changed Python symbols were established. Source coverage or supported-language analysis is insufficient; runtime behavior is unverified."
    elif not protecting_invariants:
        summary = "Python source was parsed, but no applicable verified business invariants were found for this change. Runtime behavior is unverified."
    else:
        summary = "Static relationships and invariant references were found, but no approved execution verifier ran for this external repository. Runtime behavior is unverified."
    cypher_path = f"PR#{pr_number} -> {head_sha[:8]} -> Static analysis only (execution unverified)"

    # --- Step 4: Construct Dynamic Evidence Subgraph ---
    evidence_nodes: List[Dict[str, Any]] = [
        {"id": "pr", "label": f"PR #{pr_number}", "type": "PullRequest"},
        {"id": "commit", "label": head_sha[:8], "type": "Commit"},
    ]
    evidence_edges: List[Dict[str, Any]] = [
        {"source": "pr", "target": "commit", "label": "HEAD"},
    ]

    for idx, fn in enumerate(changed_filenames[:5]):
        node_id = f"file_{idx}"
        evidence_nodes.append({"id": node_id, "label": fn.split("/")[-1], "type": "File", "path": fn})
        evidence_edges.append({"source": "commit", "target": node_id, "label": "MODIFIES"})

    for idx, sym in enumerate(modified_symbols_info[:5]):
        s_id = f"sym_{idx}"
        evidence_nodes.append({
            "id": s_id,
            "label": sym["name"],
            "type": sym.get("kind", "Function"),
            "status": sym.get("status", "MODIFIED"),
            "is_semantic": sym.get("is_semantic", True),
            "path": sym.get("path"), "line": sym.get("start"),
        })
        evidence_edges.append({"source": "commit", "target": s_id, "label": "MODIFIES"})

    for idx, cl in enumerate(impacted_callers[:4]):
        c_id = f"caller_{idx}"
        evidence_nodes.append({"id": c_id, "label": cl["caller_name"], "type": "Function"})
        target_idx = next((i for i, symbol in enumerate(modified_symbols_info[:5]) if symbol["name"] == cl.get("target_name")), None)
        if target_idx is not None:
            evidence_edges.append({"source": c_id, "target": f"sym_{target_idx}", "label": "CALLS"})

    if affected_services:
        for idx, svc in enumerate(affected_services):
            node_id = f"svc_{idx}"
            evidence_nodes.append({"id": node_id, "label": svc, "type": "Service"})
            evidence_edges.append({"source": "commit", "target": node_id, "label": "AFFECTS"})

    if invariant_id:
        evidence_nodes.append({"id": "inv", "label": invariant_id, "type": "Invariant"})
        target_src = "svc_0" if affected_services else "commit"
        evidence_edges.append({"source": target_src, "target": "inv", "label": "VIOLATES"})

    evidence_graph = {"nodes": evidence_nodes, "edges": evidence_edges}

    # Update Investigation in Database
    investigation.status = "completed"
    investigation.verdict = verdict
    investigation.confidence = confidence
    investigation.summary = summary
    investigation.report_json = json.dumps({
        "verdict": verdict,
        "confidence": confidence,
        "summary": summary,
        "invariant_id": invariant_id,
        "affected_services": affected_services,
        "cypher_path": cypher_path,
        "is_docs_only": is_docs_only,
        "changed_files": [{"path": f.get("filename"), "status": f.get("status"), "additions": f.get("additions"), "deletions": f.get("deletions")} for f in changed_files],
        "verification_method": "Read-only static AST and graph traversal; no external code execution",
        "changed_components": modified_symbols_info,
        "impacted_callers": impacted_callers,
        "covering_tests": covering_tests,
        "protecting_invariants": protecting_invariants,
    })
    investigation.evidence_graph_json = json.dumps(evidence_graph)
    investigation.completed_at = utcnow()
    db.commit()

    # Log audit event
    audit = AuditEvent(
        organization_id=repo.organization_id,
        action="pr.investigated",
        resource_type="PullRequest",
        resource_id=pr.id,
        metadata_json=json.dumps({"verdict": verdict, "commit_sha": head_sha}),
    )
    db.add(audit)
    db.commit()

    # Update GitHub Checks API and post PR Comment
    title, conclusion, text = format_check_run_markdown(
        verdict=verdict,
        pr_number=pr_number,
        head_sha=head_sha,
        invariant_id=invariant_id,
        affected_services=affected_services,
        summary=summary,
        cypher_path=cypher_path,
        base_sha=base_sha,
        changed_components=modified_symbols_info,
        impacted_callers=impacted_callers,
        covering_tests=covering_tests,
        protecting_invariants=protecting_invariants,
        is_docs_only=is_docs_only,
        repo_full_name=full_name,
    )

    if installation_id and check_run_id and owner and repo_name:
        try:
            gh_client.update_check_run(
                installation_id=installation_id,
                owner=owner,
                repo=repo_name,
                check_run_id=check_run_id,
                status="completed",
                conclusion=conclusion,
                title=title,
                summary=summary,
                text=text,
            )
        except Exception as exc:
            logger.warning("Failed to update GitHub Check Run: %s", exc)

    if installation_id and verdict == "REPRODUCED" and owner and repo_name:
        try:
            gh_client.create_pr_comment(
                installation_id=installation_id,
                owner=owner,
                repo=repo_name,
                pr_number=pr_number,
                body=text,
            )
        except Exception as exc:
            logger.warning("Failed to post GitHub PR comment: %s", exc)

    logger.info("Completed graph-native investigation for PR #%d with verdict %s", pr_number, verdict)
