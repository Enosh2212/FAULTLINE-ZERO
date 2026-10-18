"""Configuration for the FlyMemory bio-inspired associative intelligence engine."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class FlyMemoryConfig:
    """Hyperparameters for the fruit-fly olfactory hashing circuit and retriever."""

    # System activation
    enabled: bool = False
    seed: int = 42

    # Dimensions
    # d: Input feature vector dimension (Projection Neurons)
    input_dim: int = 128
    # m: High-dimensional expanded representation (Kenyon Cells = expansion_factor * input_dim)
    expansion_factor: int = 20
    # Sparsity / fan-in: Fraction of PNs connected to each KC
    sparsity: float = 0.10
    # Winner ratio: Fraction of KCs surviving Winner-Take-All inhibition (APL lateral inhibition)
    winner_ratio: float = 0.05

    # Retrieval parameters
    top_k_retrieve: int = 5
    similarity_metric: Literal["overlap", "jaccard", "hamming"] = "overlap"
    min_similarity_threshold: float = 0.10

    # Graph reranking boost
    graph_rerank_boost: float = 0.35

    # Versions
    encoder_version: str = "fly-feat-v1.0"
    projection_version: str = "fly-lsh-v1.0-d128-m2560-k128-seed42"

    @property
    def expanded_dim(self) -> int:
        """m: Number of Kenyon Cells."""
        return self.input_dim * self.expansion_factor

    @property
    def num_winners(self) -> int:
        """k: Exact number of active winners retained after Winner-Take-All."""
        return max(1, int(round(self.expanded_dim * self.winner_ratio)))

    @property
    def fan_in(self) -> int:
        """c: Number of input connections per Kenyon Cell."""
        return max(1, int(round(self.input_dim * self.sparsity)))
