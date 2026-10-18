"""Fruit-Fly-Inspired Locality-Sensitive Hashing (Fly-LSH).

Mathematically based on the olfactory circuit of Drosophila melanogaster:
Dasgupta, Stevens, and Navlakha (Science 2017)
'A neural algorithm for a fundamental computing problem'
https://doi.org/10.1126/science.aam9868

Architecture:
- Input vector x of dimension d (Projection Neurons / PNs)
- Expanded representation a of dimension m >> d (Kenyon Cells / KCs)
- Sparse random projection matrix M in {0, 1}^(d x m), where each KC receives
  input from a small subset of PNs (fan-in c << d).
- Winner-Take-All (WTA) lateral inhibition (via anterior paired lateral / APL neuron),
  forcing all but the top-k highest-activation KCs to zero.
- Output fingerprint: highly sparse binary representation with exactly k active indices.
"""
from __future__ import annotations
import math
import random
from typing import Sequence

from faultline.flymemory.config import FlyMemoryConfig

# Check if numpy is available
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class FlyHash:
    """Implements sparse random projection and Winner-Take-All sparsification."""

    def __init__(self, config: FlyMemoryConfig | None = None) -> None:
        self.config = config or FlyMemoryConfig()
        self.d = self.config.input_dim
        self.m = self.config.expanded_dim
        self.k = self.config.num_winners
        self.fan_in = self.config.fan_in
        self.seed = self.config.seed
        self.version = self.config.projection_version

        # Initialize projection connections deterministically
        self._kc_connections: list[list[int]] = []
        self._np_matrix = None
        self._build_projection_matrix()

    def _build_projection_matrix(self) -> None:
        """Constructs a deterministic sparse binary projection matrix with fan-in c per KC."""
        rng = random.Random(self.seed)

        # Build list of input indices for each of the m Kenyon Cells
        self._kc_connections = []
        for _ in range(self.m):
            # Sample exactly fan_in unique input dimensions from [0, d-1]
            connections = rng.sample(range(self.d), self.fan_in)
            connections.sort()
            self._kc_connections.append(connections)

        if HAS_NUMPY:
            # Build 2D sparse matrix of shape (d, m)
            mat = np.zeros((self.d, self.m), dtype=np.float32)
            for j, conns in enumerate(self._kc_connections):
                for i in conns:
                    mat[i, j] = 1.0
            self._np_matrix = mat

    def project(self, x: Sequence[float]) -> list[float]:
        """Projects d-dimensional input into m-dimensional expanded representation."""
        if len(x) != self.d:
            raise ValueError(f"Input vector dimension {len(x)} does not match expected {self.d}")

        if HAS_NUMPY and self._np_matrix is not None:
            x_arr = np.array(x, dtype=np.float32)
            activations = np.dot(x_arr, self._np_matrix)
            return activations.tolist()

        # Pure-Python high-performance sparse projection
        activations = [0.0] * self.m
        for j, conns in enumerate(self._kc_connections):
            act = 0.0
            for i in conns:
                act += x[i]
            activations[j] = act
        return activations

    def winner_take_all(self, activations: Sequence[float]) -> list[int]:
        """Applies Winner-Take-All lateral inhibition to select top-k dimensions.

        Uses deterministic tie-breaking: in case of equal activation, smaller index wins.
        Returns a sorted list of exactly k integer indices.
        """
        if len(activations) != self.m:
            raise ValueError(f"Activations length {len(activations)} does not match m={self.m}")

        # Pair (activation, -index) so that higher activation comes first,
        # and on ties, smaller index comes first (since -(-idx) = idx is sorted ascending)
        indexed = [(-act, idx) for idx, act in enumerate(activations)]
        indexed.sort()

        # Select top-k active winners
        winners = [idx for _, idx in indexed[: self.k]]
        winners.sort()

        if len(winners) != self.k:
            raise AssertionError(f"WTA must return exactly k={self.k} winners, got {len(winners)}")

        return winners

    def hash(self, x: Sequence[float]) -> list[int]:
        """End-to-end Fly-LSH: Sparse Projection + Winner-Take-All.

        Returns:
            list[int]: Sorted list of exactly k active winner indices in [0, m-1].
        """
        activations = self.project(x)
        return self.winner_take_all(activations)

    def to_binary_vector(self, active_indices: Sequence[int]) -> list[int]:
        """Converts sparse active indices into a full binary vector of length m."""
        vec = [0] * self.m
        for idx in active_indices:
            if 0 <= idx < self.m:
                vec[idx] = 1
        return vec

    @staticmethod
    def overlap_similarity(indices_a: Sequence[int], indices_b: Sequence[int]) -> float:
        """Calculates normalized active dimension overlap |A n B| / k."""
        if not indices_a or not indices_b:
            return 0.0
        set_a = set(indices_a)
        set_b = set(indices_b)
        intersection = len(set_a & set_b)
        denom = min(len(set_a), len(set_b))
        return intersection / denom if denom > 0 else 0.0

    @staticmethod
    def jaccard_similarity(indices_a: Sequence[int], indices_b: Sequence[int]) -> float:
        """Calculates Jaccard similarity |A n B| / |A u B|."""
        if not indices_a or not indices_b:
            return 0.0
        set_a = set(indices_a)
        set_b = set(indices_b)
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def hamming_distance(indices_a: Sequence[int], indices_b: Sequence[int], k: int) -> int:
        """Calculates Hamming distance between two binary vectors each having exactly k ones."""
        set_a = set(indices_a)
        set_b = set(indices_b)
        intersection = len(set_a & set_b)
        return 2 * (k - intersection)
