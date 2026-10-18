> Historical v0.1 notes retained for context. For the current Git workflow and verified status, use README.md, AGENT_DESIGN.md and BUILD_STATUS.md.

# Operations / developer runbook

## Start from VS Code terminal (Windows PowerShell)

```powershell
cd PATH\TO\FAULTLINE_ZERO
docker --version
docker compose version
docker compose up --build -d
docker compose ps
python scripts/smoke_test.py
```

UI: `http://localhost:8000`  
API docs: `http://localhost:8000/docs`

## Diagnostics

| Symptom | Quick checks | Likely cause |
|---|---|---|
| UI says FalkorDB disconnected | `docker compose ps`, then API logs | Graph startup or query error |
| `localhost:8000` won't load | API logs, `docker compose ps` | Port conflict or image build failure |
| Health 503 | Graph logs + `docker compose exec graph redis-cli ping` | Graph unavailable or bootstrap failure |
| Empty topology | API logs and graph health | Seeding/query parsing not working |
| Baseline and candidate ERROR | API logs; run `python -m faultline.runner_worker baseline TC-PAY-IDEMPOTENCY` from installed Python env | Fixture import or execution issue |
| Saved report vanished | Check graph volume and AOF | Volumes deleted or mismatched image data path |

## Useful operational commands

```powershell
docker compose logs -f api
docker compose logs -f graph
docker compose restart api
docker compose down
```

Do not run `docker compose down -v` if persistent reports matter.

## Verify graph after API restart

1. Run a payment investigation.
2. Record `INV-...` ID from UI or API response.
3. `docker compose restart api`.
4. Open `/api/v1/investigations/{id}`.
5. Same verdict and evidence path should return.

## Production release gate

This prototype cannot be released publicly without a real security review, isolation of any untrusted code, authenticated graph connectivity, queue and rate limits, HTTPS, dependency pinning, backups and restore testing. See `SECURITY.md`.
