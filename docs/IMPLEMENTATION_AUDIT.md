# Audit and implementation plan — 17 October 2026

Original verified baseline: 13 automated tests passed; Docker engine 29.8.2 available. Original implementation uses fixed synthetic changes, graph-required test discovery, actual bundled baseline/candidate functions, subprocess timeouts, independent assertions and graph report persistence. Optional LLMPlanner only reorders predetermined tests. It is not autonomous tool calling. Existing documentation mostly acknowledges that limitation.

Priority sequence followed:
1. Preserve legacy endpoints and scenarios.
2. Add a real, locally generated Git history with independently changed revisions and AST symbol extraction.
3. Index Git facts into the existing FalkorDB plan model; verify source before executing it.
4. Add bounded validated tool calls, observations, graph checkpoints, deterministic evidence policy and explicit fallback labeling.
5. Add actual diff/mode controls, graph evidence filtering and reproducible evaluation.
6. Verify unit tests, live Docker integration, restart persistence and browser flow; document missing external verification.

Limitations remain deliberate: only one trusted one-file commerce repository, four curated change tags, explicit service ownership, no arbitrary repository execution, no dynamic Python call graph, no GitHub integration. Provider protocol is tested with doubles; real model execution requires operator credentials.
