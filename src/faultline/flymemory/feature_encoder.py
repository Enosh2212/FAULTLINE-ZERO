"""Deterministic software incident feature encoder.

Transforms structured code, git diff, service, and invariant metadata into a
normalized fixed-dimensional continuous feature representation (dimension d).

Important:
- Uses stable cryptographic hashing (SHA-256) instead of Python's randomized hash().
- Never includes ground-truth investigation verdicts or evaluation labels in query features.
- Produces deterministic, version-controlled feature vectors.
"""
from __future__ import annotations
import hashlib
import math
import re
from typing import Any, Sequence

from faultline.flymemory.config import FlyMemoryConfig


class IncidentFeatureEncoder:
    """Encodes software investigation context into a d-dimensional feature vector."""

    def __init__(self, config: FlyMemoryConfig | None = None) -> None:
        self.config = config or FlyMemoryConfig()
        self.dim = self.config.input_dim
        self.version = self.config.encoder_version

    def _hash_to_index(self, token: str, namespace: str) -> tuple[int, float]:
        """Maps a token within a namespace to a bucket index [0, dim-1] and a sign (+1/-1)."""
        combined = f"{namespace}:{token}".encode("utf-8")
        digest = hashlib.sha256(combined).digest()
        # Derive integer bucket
        val = int.from_bytes(digest[:4], "big")
        idx = val % self.dim
        # Derive pseudo-random sign for signed feature hashing (Weinberger et al. 2009)
        sign = 1.0 if (digest[4] % 2 == 0) else -1.0
        return idx, sign

    def _extract_diff_tokens(self, diff_text: str) -> list[str]:
        """Extracts normalized identifiers and keywords from git diff hunks."""
        tokens: list[str] = []
        for line in diff_text.splitlines():
            line = line.strip()
            # Only consider added or modified lines
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
                # Extract word tokens with length >= 3
                words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", line)
                tokens.extend(w.lower() for w in words)
        return tokens[:80]  # Cap to prevent outsized diff dominance

    def encode(
        self,
        *,
        symbols: Sequence[str] = (),
        services: Sequence[str] = (),
        invariants: Sequence[str] = (),
        diff_text: str = "",
        testcases: Sequence[str] = (),
        ast_kinds: Sequence[str] = (),
        failure_patterns: Sequence[str] = (),
    ) -> list[float]:
        """Encodes investigation context into a normalized vector of length d."""
        vec = [0.0] * self.dim

        # 1. Modified Symbols (Weight: 3.0)
        for sym in symbols:
            if not sym:
                continue
            idx, sign = self._hash_to_index(sym.lower().strip(), "sym")
            vec[idx] += 3.0 * sign

        # 2. Associated Services (Weight: 2.5)
        for svc in services:
            if not svc:
                continue
            idx, sign = self._hash_to_index(svc.upper().strip(), "svc")
            vec[idx] += 2.5 * sign

        # 3. Business Invariants (Weight: 4.0 - primary semantic anchors)
        for inv in invariants:
            if not inv:
                continue
            idx, sign = self._hash_to_index(inv.upper().strip(), "inv")
            vec[idx] += 4.0 * sign

        # 4. AST Symbol Kinds (Weight: 1.0)
        for kind in ast_kinds:
            if not kind:
                continue
            idx, sign = self._hash_to_index(kind.lower().strip(), "ast")
            vec[idx] += 1.0 * sign

        # 5. Verified Failure Patterns (Weight: 3.5)
        for pat in failure_patterns:
            if not pat:
                continue
            idx, sign = self._hash_to_index(pat.lower().strip(), "pat")
            vec[idx] += 3.5 * sign

        # 6. Testcase Types / Target Test (Weight: 2.0)
        for tc in testcases:
            if not tc:
                continue
            idx, sign = self._hash_to_index(tc.strip(), "tc")
            vec[idx] += 2.0 * sign

        # 7. Git Diff Tokens (Weight: 0.5 per token)
        if diff_text:
            diff_tokens = self._extract_diff_tokens(diff_text)
            for tok in diff_tokens:
                idx, sign = self._hash_to_index(tok, "diff")
                vec[idx] += 0.5 * sign

        # L2 Normalization (ensures scale independence)
        norm_sq = sum(v * v for v in vec)
        if norm_sq > 1e-12:
            inv_norm = 1.0 / math.sqrt(norm_sq)
            vec = [v * inv_norm for v in vec]
        else:
            # Fallback for empty context: uniform low activation
            uniform = 1.0 / math.sqrt(self.dim)
            vec = [uniform] * self.dim

        return vec

    def encode_investigation_data(self, data: dict[str, Any]) -> list[float]:
        """Convenience method to encode from git_demo / API change data dictionary."""
        symbols = data.get("modified_symbols") or [s["name"] for s in data.get("symbols", [])]
        diff_text = data.get("diff", "")
        # Derive possible services/invariants from change_id or explicit fields if present
        services = data.get("services", [])
        invariants = data.get("invariants", [])
        failure_patterns = data.get("failure_patterns", [])
        testcases = data.get("testcases", [])
        ast_kinds = [s.get("kind", "") for s in data.get("symbols", []) if isinstance(s, dict)]

        return self.encode(
            symbols=symbols,
            services=services,
            invariants=invariants,
            diff_text=diff_text,
            testcases=testcases,
            ast_kinds=ast_kinds,
            failure_patterns=failure_patterns,
        )
