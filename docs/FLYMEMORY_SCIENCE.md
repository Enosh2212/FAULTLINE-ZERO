# FlyMemory — Scientific Foundation & Neuroscience Rationale

## 1. Executive Summary

**FlyMemory** is a biologically inspired sparse associative retrieval subsystem developed for **FAULTLINE ZERO**. It is based on the computational architecture of the fruit fly (*Drosophila melanogaster*) olfactory circuit, first formalized by **Dasgupta, Stevens, and Navlakha (Science, 2017; doi:10.1126/science.aam9868)**.

FlyMemory enables FAULTLINE ZERO's graph-native AI agent to map code changes, diff metrics, affected AST nodes, and invariant violation hypotheses into high-dimensional sparse binary representations (sparse associative fingerprints). When an investigation agent analyzes a pull request or code diff, FlyMemory retrieves structurally similar historical incidents from FalkorDB to generate targeted counterexample exploration plans.

---

## 2. Scientific Disclaimer & Boundaries

To preserve scientific integrity and avoid marketing exaggerations common in AI tooling, the following boundaries are formally stated:

1. **Not a Brain Simulation**: FlyMemory does not simulate a biological brain, Drosophila connectome, biophysical neuron dynamics, or synaptic plasticity (STDP).
2. **Not Neural Consciousness**: It has no subjective awareness, cognitive reasoning, or biological learning.
3. **Not a Foundation Model**: It does not replace LLM reasoning or deep learning embeddings; it operates as an exact, deterministic, sparse locality-sensitive hash (LSH).
4. **Hypothesis Generation Only**: Similarity to a past incident is **never treated as proof** of a current regression. In FAULTLINE ZERO, an invariant violation is only confirmed when the Differential Execution Runner reproduces an actual test or invariant failure between baseline and candidate commits.

---

## 3. The Biological Olfactory Circuit

The fruit fly olfactory system is an evolutionary masterpiece of sparse associative recognition. A fly must identify thousands of odor blends across noisy environmental gradients using only ~50 odorant receptor types, recognizing familiar odors while generalizing across intensity fluctuations.

The biological circuit consists of four primary neuronal stages:

```
                  ┌──────────────────────────────────────────────┐
                  │       Drosophila Olfactory Pathway           │
                  └──────────────────────────────────────────────┘

  Odorant Molecules
         │
         ▼
 ┌───────────────┐
 │   Antenna &   │   50-100 Odorant Receptor Neurons (ORNs)
 │ Maxillary Palp│   Continuous chemical binding signals
 └───────┬───────┘
         │
         ▼
 ┌───────────────┐
 │   Antennal    │   Projection Neurons (PNs)
 │     Lobe      │   Dimension d ≈ 50-100 (normalized odor spectrum)
 └───────┬───────┘
         │
         │  Sparse Random Synaptic Projection (~10% connectivity)
         │  Feedforward expansion into higher dimension (20x-40x)
         ▼
 ┌───────────────┐   Kenyon Cells (KCs) in Mushroom Body
 │ Mushroom Body │   Dimension m ≈ 2,000 (m >> d)
 │  Kenyon Cells │   Linear summation: a = W · x
 └───────┬───────┘
         ▲
         │ Lateral Inhibition (GABAergic feedback)
 ┌───────┴───────┐
 │   APL Neuron  │   Anterior Paired Lateral Neuron
 │ (Interneuron) │   Enforces Winner-Take-All (WTA) sparsity (~5% winners)
 └───────┬───────┘
         │
         │ Sparse Binary Representation (1 if top-k KC, else 0)
         ▼
 ┌───────────────┐
 │ Mushroom Body │   Mushroom Body Output Neurons (MBONs)
 │ Output (MBON) │   Synaptic weights associate odor pattern with valence/memory
 └───────────────┘
```

### Neurobiological Mapping to FlyMemory

| Biological Stage | Drosophila Circuit | FlyMemory Computational Primitive |
| :--- | :--- | :--- |
| **Input Layer** | Antennal Lobe Projection Neurons ($d \approx 50$) | **Feature Encoder**: Continuous normalized vector $\mathbf{x} \in [0, 1]^d$ ($d=128$) encoding AST diffs, touched components, and invariant semantics. |
| **Expansion Projection** | Random PN $\to$ Kenyon Cell synapses ($10\%$ density) | **Sparse Random Projection Matrix** $\mathbf{W} \in \{0, 1\}^{m \times d}$ ($m=2560$, sparsity $\rho=0.10$, fixed seed). |
| **Lateral Inhibition** | APL (Anterior Paired Lateral) GABAergic interneuron | **Winner-Take-All (WTA) Sparsification**: Identifies exact top-$k$ active units ($k=128$, top $5\%$), zeroing out the remaining $95\%$. |
| **Associative Output** | Kenyon Cell $\to$ MBON synapses | **Binary Memory Retrieval**: Overlap / Jaccard similarity across sparse binary hashes, validated through FalkorDB graph topology. |

---

## 4. Mathematical Formulation

### 4.1 Feature Vector Construction ($\mathbf{x}$)
Given a code change $\mathcal{C} = (\Delta_{\text{diff}}, \mathcal{A}_{\text{AST}}, \mathcal{I}_{\text{invariants}})$, the deterministic feature encoder computes a continuous vector $\mathbf{x} \in \mathbb{R}^d$ ($d=128$):
$$\mathbf{x} = \frac{\mathbf{v}}{\|\mathbf{v}\|_2 + \epsilon}, \quad v_i \ge 0$$
Features include file-level churn, AST mutation types (function signature changes, branch additions, callsite shifts), touched subsystem clusters, and invariant rule tags. Ground-truth test outcomes or evaluation labels are strictly excluded to prevent data leakage.

### 4.2 Sparse Random Expansion ($\mathbf{a}$)
Unlike classical random projection which uses dense Gaussian matrices $\mathbf{W} \sim \mathcal{N}(0, 1)$, Fly-LSH uses a **sparse binary projection matrix**:
$$\mathbf{W} \in \{0, 1\}^{m \times d}, \quad \mathbb{P}(W_{ij} = 1) = \rho = 0.10$$
For an expansion factor $\gamma = 20$, the expanded dimensionality is $m = \gamma \cdot d = 2560$.
The pre-inhibition activation vector $\mathbf{a} \in \mathbb{R}^m$ is computed via:
$$\mathbf{a} = \mathbf{W} \mathbf{x}$$
Because $\mathbf{W}$ is binary and sparse, each Kenyon cell computes the sum of approximately $\rho \cdot d \approx 13$ randomly sampled input features.

### 4.3 Winner-Take-All (WTA) Lateral Inhibition ($\mathbf{h}$)
The APL neuron in the fruit fly acts as a global inhibitory circuit that silences all but the most strongly activated Kenyon cells. In FlyMemory, this is formalized as an exact top-$k$ selection:
$$k = \lfloor \mu \cdot m \rfloor = \lfloor 0.05 \times 2560 \rfloor = 128$$
$$\text{threshold } \tau = \text{k-th largest value in } \mathbf{a}$$
$$h_j = \begin{cases} 1 & \text{if } a_j \ge \tau \text{ (with deterministic tie-breaking)} \\ 0 & \text{otherwise} \end{cases}$$
The resulting binary hash $\mathbf{h} \in \{0, 1\}^m$ has an exact Hamming weight $\|\mathbf{h}\|_1 = k = 128$.

### 4.4 Associative Similarity Metrics
To compare an incoming change $\mathbf{h}_q$ against an indexed historical incident $\mathbf{h}_i$:

1. **Overlap Similarity** (Active Coincidence Count):
   $$\text{Sim}_{\text{overlap}}(\mathbf{h}_q, \mathbf{h}_i) = \frac{\mathbf{h}_q \cdot \mathbf{h}_i}{k} = \frac{|\{j : h_{q,j} = 1 \land h_{i,j} = 1\}|}{k}$$
2. **Jaccard Similarity**:
   $$\text{Sim}_{\text{Jaccard}}(\mathbf{h}_q, \mathbf{h}_i) = \frac{|\{j : h_{q,j} = 1 \land h_{i,j} = 1\}|}{|\{j : h_{q,j} = 1 \lor h_{i,j} = 1\}|} = \frac{\mathbf{h}_q \cdot \mathbf{h}_i}{2k - \mathbf{h}_q \cdot \mathbf{h}_i}$$
3. **Normalized Hamming Distance**:
   $$D_{\text{Hamming}}(\mathbf{h}_q, \mathbf{h}_i) = \frac{1}{m} \sum_{j=1}^m |h_{q,j} - h_{i,j}| = \frac{2(k - \mathbf{h}_q \cdot \mathbf{h}_i)}{m}$$

---

## 5. Fly-LSH vs. Classical Random Projection LSH

The seminal work of Dasgupta et al. (2017) demonstrated that the fly olfactory circuit solves the Nearest Neighbors problem using a fundamentally different geometry than conventional computer science algorithms (such as Charikar's SimHash or Indyk-Motwani LSH):

| Attribute | Classical LSH (SimHash / Indyk-Motwani) | Fly-LSH (Dasgupta et al. 2017) / FlyMemory |
| :--- | :--- | :--- |
| **Dimensional Geometry** | **Dimensionality Reduction** ($d \to b$, where $b \ll d$) | **Dimensionality Expansion** ($d \to m$, where $m \gg d$, e.g., $20\times$) |
| **Projection Matrix** | Dense Gaussian ($\mathbf{W} \sim \mathcal{N}(0, 1)$ or dense Rademacher) | **Sparse Binary** ($\mathbf{W} \in \{0, 1\}$, $\approx 10\%$ ones) |
| **Non-Linear Sparsification** | Sign thresholding at zero ($\text{sgn}(Wx)$) | **Winner-Take-All lateral inhibition** (top $5\%$ winners) |
| **Representation Type** | Dense bitstring | **Ultra-sparse high-dimensional binary vector** |
| **Noise Resilience** | Sensitive to perturbations near hyperplane boundaries | Highly robust due to distributed sparse tag representations |
| **Biological Analogue** | None (pure numerical algebra) | Olfactory receptor to Kenyon cell mushroom body projection |

---

## 6. Graph Grounding: FalkorDB Synergy

A pure vector or hash retrieval system suffers from the "hallucinated analog" problem: retrieving an incident that looks syntactically similar in token space but has no structural, module, or call-graph relationship in the actual codebase.

FlyMemory solves this by coupling the sparse Fly-LSH retrieval with **FalkorDB topological reranking**:
1. **Candidate Retrieval**: Fly-LSH retrieves the top-$K$ historical incidents matching the sparse feature hash.
2. **Graph Path Verification**: For each candidate incident, FalkorDB evaluates whether the incident's recorded affected components share graph paths (`[:CALLS]`, `[:IMPORTS]`, `[:DEPENDS_ON]`, `[:VIOLATES]`) with the currently changed symbols.
3. **Composite Scoring**:
   $$\text{Score}_{\text{composite}} = (1 - \alpha) \cdot \text{Sim}_{\text{FlyHash}} + \alpha \cdot \text{Score}_{\text{GraphPath}}$$
   where $\alpha = 0.35$ provides graph grounding without overwhelming the associative pattern match.

If no valid topological connection exists in FalkorDB, the incident's ranking is down-weighted and the agent is alerted that the historical match is purely lexical/phenotypic rather than structural.

---

## 7. References

1. **Dasgupta, S., Stevens, C. F., & Navlakha, S.** (2017). *A neural algorithm for fundamental computing: How the fruit fly computes similarity*. **Science**, 358(6364), 793–796. [doi:10.1126/science.aam9868](https://doi.org/10.1126/science.aam9868).
2. **Charikar, M. S.** (2002). *Similarity estimation techniques from rounding algorithms*. Proceedings of the 34th Annual ACM Symposium on Theory of Computing (STOC '02), 380–388.
3. **Indyk, P., & Motwani, R.** (1998). *Approximate nearest neighbors: towards removing the curse of dimensionality*. Proceedings of the 30th Annual ACM Symposium on Theory of Computing (STOC '98), 604–613.
4. **Caron, S. J., Ruta, V., Abbott, L. F., & Axel, R.** (2013). *Random convergence of olfactory inputs in the Drosophila mushroom body*. **Nature**, 497(7447), 113–117.
