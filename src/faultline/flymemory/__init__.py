"""FlyMemory: Bio-Inspired Associative Incident Memory.

Based on the fruit fly (Drosophila melanogaster) olfactory circuit architecture
described in Dasgupta, Stevens, and Navlakha (Science, 2017).

Computational principles:
1. Deterministic software incident feature encoding (input dimension d).
2. Sparse binary random projection into high-dimensional space (expansion factor m >> d).
3. Winner-Take-All (WTA) inhibitory sparsification (exact top-k active dimensions).
4. Sparse associative similarity retrieval (Hamming, Jaccard, Overlap).
5. FalkorDB graph-grounded evidence verification and topological reranking.
"""

from faultline.flymemory.config import FlyMemoryConfig
from faultline.flymemory.feature_encoder import IncidentFeatureEncoder
from faultline.flymemory.flyhash import FlyHash
from faultline.flymemory.retriever import MemoryRetriever, RetrievedMemory
from faultline.flymemory.store import FlyMemoryStore, IncidentMemory

__all__ = [
    "FlyMemoryConfig",
    "IncidentFeatureEncoder",
    "FlyHash",
    "FlyMemoryStore",
    "IncidentMemory",
    "MemoryRetriever",
    "RetrievedMemory",
]
