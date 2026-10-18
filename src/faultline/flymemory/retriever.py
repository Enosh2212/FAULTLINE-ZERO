"""Graph-Grounded FlyMemory Retriever.

Combines fruit-fly-inspired sparse associative retrieval with FalkorDB
graph verification to ground historical recall in verifiable software dependencies.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import logging
from typing import Any, Sequence

from faultline.flymemory.config import FlyMemoryConfig
from faultline.flymemory.feature_encoder import IncidentFeatureEncoder
from faultline.flymemory.flyhash import FlyHash
from faultline.flymemory.store import FlyMemoryStore, IncidentMemory, get_flymemory_store

logger = logging.getLogger(__name__)


@dataclass
class RetrievedMemory:
    """A ranked historical incident memory with graph grounding and explanation."""

    incident_id: str
    memory_id: str
    title: str
    change_id: str
    similarity_score: float
    final_score: float
    graph_verified: bool
    verdict: str
    historical_test_strategy: str
    shared_symbols: list[str]
    shared_services: list[str]
    shared_invariants: list[str]
    evidence_path: list[str]
    relevance_explanation: str
    caveat: str = "Similarity hypothesis only; does not prove current regression without independent differential execution."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MemoryRetriever:
    """Retrieves and graph-verifies historical incident memories for an investigation."""

    def __init__(
        self,
        config: FlyMemoryConfig | None = None,
        store: FlyMemoryStore | None = None,
        encoder: IncidentFeatureEncoder | None = None,
        flyhash: FlyHash | None = None,
    ) -> None:
        self.config = config or FlyMemoryConfig()
        self.store = store or get_flymemory_store()
        self.encoder = encoder or IncidentFeatureEncoder(self.config)
        self.flyhash = flyhash or FlyHash(self.config)

    def _verify_graph_connection(
        self,
        graph_repo: Any,
        current_symbols: Sequence[str],
        candidate_services: Sequence[str],
        candidate_invariants: Sequence[str],
    ) -> tuple[bool, list[str]]:
        """Checks if historical services/invariants connect to current symbols in FalkorDB."""
        if not hasattr(graph_repo, "_read") or not current_symbols:
            return False, []

        verified = False
        matching_paths: list[str] = []

        # Check each current symbol's reachability to candidate invariants in FalkorDB
        for sym in current_symbols:
            for inv in candidate_invariants:
                cypher = """
                MATCH (s:Symbol {name: $sym})-[:PART_OF]->(seed:Service)
                MATCH (seed)-[:CALLS*0..3]->(target:Service)-[:ENFORCES]->(i:Invariant {id: $inv})
                RETURN seed.id, target.id
                LIMIT 1
                """
                try:
                    res = graph_repo._read(cypher, sym=sym, inv=inv)
                    if res:
                        verified = True
                        seed_svc, target_svc = res[0]
                        matching_paths.append(f"{sym} -> {seed_svc} -> {target_svc} -> {inv}")
                except Exception:
                    pass

        return verified, matching_paths

    def retrieve(
        self,
        repo_id: str,
        current_context: dict[str, Any],
        graph_repo: Any | None = None,
        top_k: int = 5,
    ) -> list[RetrievedMemory]:
        """Performs associative FlyMemory retrieval with optional FalkorDB topological verification."""
        # 1. Feature encoding of current investigation context
        feature_vec = self.encoder.encode_investigation_data(current_context)

        # 2. Compute Fly-LSH sparse fingerprint (exact top-k active winners)
        query_fingerprint = self.flyhash.hash(feature_vec)

        # 3. Retrieve associative candidates from store
        candidates = self.store.search_similar(
            repo_id=repo_id,
            query_indices=query_fingerprint,
            top_k=top_k * 2,  # Fetch slightly wider pool for graph reranking
            min_threshold=self.config.min_similarity_threshold,
            metric=self.config.similarity_metric,
        )

        current_symbols = current_context.get("modified_symbols") or [
            s["name"] for s in current_context.get("symbols", []) if isinstance(s, dict)
        ]
        current_services = set(current_context.get("services", []))
        current_invariants = set(current_context.get("invariants", []))

        results: list[RetrievedMemory] = []

        for mem, sim_score in candidates:
            # Overlap analysis
            shared_syms = [s for s in mem.symbols if s in current_symbols]
            shared_svcs = [s for s in mem.services if s in current_services]
            shared_invs = [i for i in mem.invariants if i in current_invariants]

            # FalkorDB graph topological verification
            graph_verified = False
            verified_paths: list[str] = []
            if graph_repo is not None:
                graph_verified, verified_paths = self._verify_graph_connection(
                    graph_repo, current_symbols, mem.services, mem.invariants
                )
            elif shared_invs or shared_svcs:
                graph_verified = True

            # Calculate final score with graph boost
            if graph_verified:
                final_score = min(1.0, sim_score + self.config.graph_rerank_boost * (1.0 - sim_score))
            else:
                final_score = sim_score

            # Formulate plain-English explanation
            explanation_parts = []
            explanation_parts.append(f"Historical incident '{mem.title}' shares {int(sim_score * 100)}% sparse pattern overlap.")
            if shared_invs:
                explanation_parts.append(f"Common business invariants: {', '.join(shared_invs)}.")
            if shared_svcs:
                explanation_parts.append(f"Common service boundaries: {', '.join(shared_svcs)}.")
            if graph_verified and verified_paths:
                explanation_parts.append(f"FalkorDB verified connection: {verified_paths[0]}.")
            if mem.test_strategy:
                explanation_parts.append(f"Previously effective test strategy: {mem.test_strategy}.")

            explanation = " ".join(explanation_parts)

            results.append(
                RetrievedMemory(
                    incident_id=mem.incident_id,
                    memory_id=mem.id,
                    title=mem.title,
                    change_id=mem.change_id,
                    similarity_score=round(sim_score, 4),
                    final_score=round(final_score, 4),
                    graph_verified=graph_verified,
                    verdict=mem.verdict,
                    historical_test_strategy=mem.test_strategy,
                    shared_symbols=shared_syms,
                    shared_services=shared_svcs,
                    shared_invariants=shared_invs,
                    evidence_path=mem.evidence_path,
                    relevance_explanation=explanation,
                )
            )

        # Sort descending by final graph-boosted score
        results.sort(key=lambda r: r.final_score, reverse=True)
        return results[:top_k]
