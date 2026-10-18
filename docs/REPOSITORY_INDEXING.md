# Repository indexing

`repository_indexer.py` reads immutable local Git objects. It does not check out a candidate, import repository modules, run tests, run hooks or execute repository source. Git subprocesses use argument arrays, disabled hooks and global config, no interactive prompting, bounded timeouts, and validated revision references.

Supported extraction: Git commit SHA/parents/date/subject; tree paths; Python files, functions, async functions and classes with line spans; import records; test-file recognition and assertion text; Markdown/README/configuration/API-specification text. API specifications are identified and cited as text, not converted into a complete API ontology. Dynamic, external, builtin and shadowed call targets remain explicitly unresolved. No relationships are guessed from similar names.

Bounds: 500 regular files per supported tree, 512KB per supported text blob, an 8MB retained text budget, and skipped symlink/submodule objects. Supported languages for semantic relationships are Python only; Markdown and common config/specification formats provide documentation. The parser schema version is stored with snapshots.

Incremental operation compares content blobs with a prior repository snapshot. Unchanged file AST records are reused; changed files are parsed again; modified and removed symbols and deleted files are recorded. Each immutable revision receives scoped graph entities, preserving earlier contexts. This avoids destructive graph reconstruction. A new revision still materializes its own graph projection; structural sharing of graph records is not implemented. Git blobs are still read to collect the current source view.

If an old indexed revision no longer exists in a rebuilt demo clone, its persisted context can remain historical; it is never confused with the current Git SHA. Query callers always provide repository and revision scope.

Web demonstration:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/context/understanding
Invoke-RestMethod http://localhost:8000/api/v1/context/index -Method Post -ContentType application/json -Body '{"revision":"baseline"}'
Invoke-RestMethod http://localhost:8000/api/v1/context/change/payment
```

Independent source-only demonstration, without a payment/change ID:

```powershell
docker compose exec -T api python scripts/context_demo.py
```

Operator source-only CLI for a local registered/controlled checkout visible to the process:

```text
python -m faultline.context_graph_builder --root /path/to/local/git --repository example-project --revision HEAD
```

The generic CLI imports no trusted-commerce declarations and enables no execution. Do not advertise it as public GitHub repository support.
