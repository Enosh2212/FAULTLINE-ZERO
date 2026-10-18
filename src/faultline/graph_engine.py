"""FalkorDB graph engine for repository intelligence, version-aware snapshots,
and change impact traversal.

Strictly scopes every Cypher query by tenant, repository, and snapshot revision.
Never executes arbitrary code; operates entirely on static AST facts and verified graph nodes.
"""
from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from falkordb import FalkorDB
except ImportError:
    FalkorDB = None

from faultline.code_relationship_extractor import extract_relationships
from faultline.config import get_settings
from faultline.graph_repository import GraphUnavailable

logger = logging.getLogger("faultline.graph_engine")

SUPPORTED_GRAPH_NODES = {
    "Repository",
    "Snapshot",
    "Commit",
    "File",
    "Module",
    "Class",
    "Function",
    "Test",
    "VerifiedInvariant",
    "PullRequest",
}

SUPPORTED_GRAPH_RELATIONS = {
    "CONTAINS",
    "DEFINES",
    "IMPORTS",
    "CALLS",
    "DEPENDS_ON",
    "TESTS",
    "MODIFIES",
    "PROTECTS",
    "HEAD",
    "REFERENCES",
}


def sanitize_graph_identifier(value: str) -> str:
    """Sanitizes names for safe FalkorDB graph selection."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", value.strip().lower())
    return cleaned[:48] or "default"


class FalkorRepositoryGraph:
    """Version-aware, tenant-isolated property graph manager backed by FalkorDB."""

    def __init__(self, tenant_slug: str, settings: Optional[Any] = None):
        self.settings = settings or get_settings()
        self.tenant_slug = sanitize_graph_identifier(tenant_slug)
        self.graph_name = f"fz_tenant_{self.tenant_slug}"
        self._db: Optional[FalkorDB] = None
        self._graph = None

    @property
    def graph_id(self) -> str:
        return self.graph_name

    @property
    def graph(self):
        if self._graph is None:
            if FalkorDB is None:
                raise GraphUnavailable(f"FalkorDB library not installed; cannot connect to {self.graph_name}")
            try:
                self._db = FalkorDB(
                    host=self.settings.graph_host,
                    port=self.settings.graph_port,
                    password=self.settings.graph_password,
                )
                self._graph = self._db.select_graph(self.graph_name)
            except Exception as exc:
                raise GraphUnavailable(f"FalkorDB unavailable for {self.graph_name}: {exc}") from exc
        return self._graph

    def read(self, query: str, **params) -> List[Any]:
        """Executes a read-only Cypher query with strict parameter binding."""
        try:
            return self.graph.ro_query(query, params=params).result_set
        except Exception as exc:
            raise GraphUnavailable(f"Graph read failed: {exc}") from exc

    def write(self, query: str, **params) -> List[Any]:
        """Executes a mutating Cypher query with strict parameter binding."""
        try:
            return self.graph.query(query, params=params).result_set
        except Exception as exc:
            raise GraphUnavailable(f"Graph write failed: {exc}") from exc

    def delete_graph(self) -> None:
        """Completely drops the tenant graph upon access revocation."""
        try:
            self.graph.delete()
            self._graph = None
            logger.info("Deleted FalkorDB graph %s", self.graph_name)
        except Exception as exc:
            logger.warning("Could not delete graph %s: %s", self.graph_name, exc)

    def scoped_id(self, repo: str, revision: str, kind: str, name: str) -> str:
        """Generates a stable, globally unique node identifier scoped by tenant, repo, and commit SHA."""
        return f"{self.tenant_slug}:{repo}@{revision}:{kind}:{name}"

    def build_and_save_snapshot(
        self,
        index: Dict[str, Any],
        organization_id: str,
        invariants: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Constructs and persists the version-aware repository property graph in FalkorDB.
        Avoids storing full raw source code; indexes symbols, structural relationships, calls, and tests.
        """
        started = time.perf_counter()
        repo = index["repository"]
        revision = index["revision"]

        # Extract relationships (IMPORTS, DEFINES, CALLS, REFERENCES, etc.)
        extracted = extract_relationships(index)
        edges: List[Dict[str, Any]] = []

        nodes: Dict[str, Dict[str, Any]] = {}

        def add_node(node_id: str, kind: str, name: str, **extra):
            nodes[node_id] = {
                "id": node_id,
                "kind": kind,
                "name": name,
                "tenant_id": organization_id,
                "repository": repo,
                "revision": revision,
                **extra,
            }
            return node_id

        def add_edge(source_id: str, relation: str, target_id: str, **extra):
            if relation in SUPPORTED_GRAPH_RELATIONS:
                edges.append({
                    "source": source_id,
                    "relation": relation,
                    "target": target_id,
                    "tenant_id": organization_id,
                    "repository": repo,
                    "revision": revision,
                    **extra,
                })

        # 1. Root Repository & Snapshot Nodes
        repo_node_id = self.scoped_id(repo, "global", "repo", repo)
        add_node(repo_node_id, "Repository", repo)

        snap_node_id = self.scoped_id(repo, revision, "snapshot", "head")
        add_node(snap_node_id, "Snapshot", f"Snapshot {revision[:8]}")
        add_edge(repo_node_id, "CONTAINS", snap_node_id)

        commit_node_id = self.scoped_id(repo, revision, "commit", revision[:8])
        add_node(commit_node_id, "Commit", revision[:8], full_sha=revision)
        add_edge(snap_node_id, "CONTAINS", commit_node_id)

        # 2. Files, Modules, Classes, Functions
        for f in index.get("files", []):
            path = f["path"]
            f_id = self.scoped_id(repo, revision, "file", path)
            add_node(f_id, "File", path, path=path, language=f.get("language", "Unknown"), is_test=f.get("is_test", False))
            add_edge(commit_node_id, "CONTAINS", f_id)

            # Module node
            mod_name = path.removesuffix(".py").replace("/", ".")
            mod_id = self.scoped_id(repo, revision, "module", mod_name)
            add_node(mod_id, "Module", mod_name, path=path)
            add_edge(f_id, "DEFINES", mod_id)

            for sym in f.get("symbols", []):
                sym_name = sym["name"]
                sym_kind = sym.get("kind", "FunctionDef")
                target_kind = "Class" if sym_kind == "ClassDef" else "Function"
                if f.get("is_test") and target_kind == "Function":
                    target_kind = "Test"

                node_id = self.scoped_id(repo, revision, target_kind.lower(), f"{path}#{sym_name}")
                add_node(
                    node_id,
                    target_kind,
                    sym_name,
                    path=path,
                    start_line=sym.get("start", 1),
                    end_line=sym.get("end", 1),
                    parent=sym.get("parent"),
                    fingerprint=sym.get("fingerprint"),
                )

                if sym.get("parent"):
                    parent_kind = "class"
                    parent_node_id = self.scoped_id(repo, revision, parent_kind, f"{path}#{sym['parent']}")
                    add_edge(parent_node_id, "DEFINES", node_id)
                else:
                    add_edge(f_id, "DEFINES", node_id)

        # 3. Add Extracted Relationship Edges (CALLS, IMPORTS, TESTS, etc.)
        for e in extracted.get("edges", []):
            src_str = e.get("source", "")
            tgt_str = e.get("target", "")
            rel = e.get("relation", "")

            # Remap legacy scoped IDs to versioned tenant scoped IDs
            src_node = self._normalize_edge_id(src_str, repo, revision)
            tgt_node = self._normalize_edge_id(tgt_str, repo, revision)

            if rel == "REFERENCES":
                # Convert test references to explicit TESTS edge
                rel = "TESTS"

            if src_node and tgt_node and src_node in nodes and tgt_node in nodes:
                add_edge(src_node, rel, tgt_node, line=e.get("provenance", {}).get("line"))

        # 4. Verified Invariants (if provided or discoverable)
        for inv in invariants or []:
            inv_id = inv.get("id")
            if inv_id:
                inv_node_id = self.scoped_id(repo, revision, "invariant", inv_id)
                add_node(inv_node_id, "VerifiedInvariant", inv.get("name", inv_id), description=inv.get("description", ""))
                for target_symbol in inv.get("target_symbols", []):
                    # Link to function if exists
                    match = next((nid for nid, n in nodes.items() if n["name"] == target_symbol), None)
                    if match:
                        add_edge(inv_node_id, "PROTECTS", match)

        # 5. Persist to FalkorDB
        # Group nodes by kind
        grouped_nodes = defaultdict(list)
        for nid, n in nodes.items():
            grouped_nodes[n["kind"]].append(n)

        for kind, kind_nodes in grouped_nodes.items():
            self.write(
                f"""UNWIND $rows AS row
                MERGE (n:{kind} {{id: row.id}})
                SET n.name = row.name,
                    n.tenant_id = row.tenant_id,
                    n.repository = row.repository,
                    n.revision = row.revision,
                    n.path = row.path,
                    n.start_line = row.start_line,
                    n.end_line = row.end_line,
                    n.fingerprint = row.fingerprint""",
                rows=kind_nodes,
            )

        # Group edges by relation
        grouped_edges = defaultdict(list)
        for e in edges:
            grouped_edges[e["relation"]].append(e)

        for rel, rel_edges in grouped_edges.items():
            self.write(
                f"""UNWIND $rows AS row
                MATCH (a {{id: row.source, revision: row.revision}}),
                      (b {{id: row.target, revision: row.revision}})
                MERGE (a)-[r:{rel}]->(b)
                SET r.tenant_id = row.tenant_id,
                    r.repository = row.repository,
                    r.revision = row.revision,
                    r.line = row.line""",
                rows=rel_edges,
            )

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "Persisted %d nodes and %d edges for %s@%s in %0.2fms",
            len(nodes), len(edges), repo, revision[:8], duration_ms
        )

        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "persisted_ms": duration_ms,
            "revision": revision,
            "repository": repo,
        }

    def _normalize_edge_id(self, raw_id: str, repo: str, revision: str) -> Optional[str]:
        """Converts raw extractor scoped ID into tenant version-aware ID."""
        if ":" not in raw_id:
            return None
        parts = raw_id.split(":", 2)
        if len(parts) >= 3:
            kind, name = parts[1], parts[2]
            if kind == "symbol":
                # Determine if function or class
                return self.scoped_id(repo, revision, "function", name)
            return self.scoped_id(repo, revision, kind, name)
        return None

    def find_impacted_callers(
        self,
        repo: str,
        revision: str,
        symbol_names: List[str],
        max_depth: int = 3,
    ) -> List[Dict[str, Any]]:
        """Traverses upstream CALLS relationships in FalkorDB to discover callers within blast radius."""
        if not symbol_names:
            return []

        query = f"""
        MATCH path = (caller:Function)-[:CALLS*1..{max_depth}]->(target:Function)
        WHERE target.repository = $repo
          AND target.revision = $revision
          AND target.name IN $symbol_names
        RETURN DISTINCT caller.name, caller.path, caller.start_line, target.name, length(path) as depth
        ORDER BY depth ASC
        LIMIT 30
        """
        try:
            rows = self.read(query, repo=repo, revision=revision, symbol_names=symbol_names)
        except Exception as exc:
            logger.warning("find_impacted_callers non-fatal query error: %s", exc)
            return []
        results = []
        for r in rows:
            results.append({
                "caller_name": r[0],
                "caller_path": r[1],
                "caller_line": r[2],
                "target_name": r[3],
                "depth": r[4],
            })
        return results

    def find_covering_tests(
        self,
        repo: str,
        revision: str,
        symbol_names: List[str],
    ) -> List[Dict[str, Any]]:
        """Finds tests that directly or indirectly test the modified symbols."""
        if not symbol_names:
            return []

        query = """
        MATCH (t:Test)-[:TESTS|CALLS*1..2]->(target:Function)
        WHERE target.repository = $repo
          AND target.revision = $revision
          AND target.name IN $symbol_names
        RETURN DISTINCT t.name, t.path, target.name
        LIMIT 25
        """
        try:
            rows = self.read(query, repo=repo, revision=revision, symbol_names=symbol_names)
        except Exception as exc:
            logger.warning("find_covering_tests non-fatal query error: %s", exc)
            return []
        results = []
        for r in rows:
            results.append({
                "test_name": r[0],
                "test_path": r[1],
                "tested_symbol": r[2],
            })
        return results

    def find_protecting_invariants(
        self,
        repo: str,
        revision: str,
        symbol_names: List[str],
    ) -> List[Dict[str, Any]]:
        """Finds verified business invariants associated with the modified symbols."""
        if not symbol_names:
            return []

        query = """
        MATCH (inv:VerifiedInvariant)-[:PROTECTS]->(target:Function)
        WHERE target.repository = $repo
          AND target.revision = $revision
          AND target.name IN $symbol_names
        RETURN DISTINCT inv.name, inv.description, target.name
        LIMIT 20
        """
        try:
            rows = self.read(query, repo=repo, revision=revision, symbol_names=symbol_names)
        except Exception as exc:
            logger.warning("find_protecting_invariants non-fatal query error: %s", exc)
            return []
        results = []
        for r in rows:
            results.append({
                "invariant_name": r[0],
                "description": r[1],
                "target_symbol": r[2],
            })
        return results

    def get_graph_summary(self, repo: str, revision: str) -> Dict[str, Any]:
        """Returns statistics on the indexed repository graph."""
        try:
            node_counts = self.read(
                """MATCH (n) WHERE n.repository = $repo AND n.revision = $revision
                   RETURN labels(n)[0] as kind, count(n) as cnt""",
                repo=repo, revision=revision,
            )
            edge_counts = self.read(
                """MATCH (a)-[r]->(b) WHERE r.repository = $repo AND r.revision = $revision
                   RETURN type(r) as rel, count(r) as cnt""",
                repo=repo, revision=revision,
            )
            return {
                "nodes_by_type": {r[0]: r[1] for r in node_counts if r},
                "edges_by_type": {r[0]: r[1] for r in edge_counts if r},
                "total_nodes": sum(r[1] for r in node_counts if r),
                "total_edges": sum(r[1] for r in edge_counts if r),
            }
        except Exception as exc:
            logger.debug("Graph summary note: %s", exc)
            return {"total_nodes": 0, "total_edges": 0, "nodes_by_type": {}, "edges_by_type": {}}
