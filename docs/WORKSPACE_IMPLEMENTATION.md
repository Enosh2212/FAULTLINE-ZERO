# Authenticated workspace integration

## Architecture and audit

The application uses FastAPI, SQLAlchemy and static HTML/native JavaScript modules. The public landing page, Firebase login/register, trusted commerce investigation and existing Cytoscape/ELK infrastructure are retained. No frontend migration or additional package is required.

Previously, operational pages shared an oversized engineering-demo layout. Authentication opened a generic GitHub SaaS page; missing API data could appear as empty lists, a metadata refresh could claim a successful GitHub sync, and an installation redirect could attach an installation without verifying the signed-in user's GitHub access. Webhooks also implicitly created workspace connections. These were unsuitable for a multi-tenant product.

## Navigation and screens

- The existing **Investigation** navigation button opens the authenticated workspace. `/workspace` defaults to `#workspace/overview`; unauthenticated visits redirect to the existing login page.
- Sidebar routes: `#workspace/overview`, `/repositories`, `/repositories/{id}`, `/prs`, `/investigations`, `/investigations/{id}`, `/graph`, `/activity`, `/settings` (all prefixed `#workspace`).
- Zero-repository workspaces see onboarding rather than commerce fixtures. Repository selection is refresh-safe because verified repository candidates are saved inactive; starting an index activates the selected repository.
- The existing `/#investigation` commerce experience remains an explicitly isolated Demo/Playground. Its context label and workspace link are **inside the Investigation content**, not a new banner above the header.
- A responsive drawer, workspace selector, search over loaded workspace records, repository/verdict/state filters, evidence inspector, graph node list/inspector and activity retry provide real interactions.
- Process status and verdict are separate. Inconclusive is amber/neutral; CLEAN is explicitly scoped. The external PR handler no longer manufactures REPRODUCED/CLEAN from keyword matches or queries the synthetic demo graph.

## Source files

- `src/faultline/web/workspace.js`: shell, onboarding, shared lists/states, operational screens, polling and actions.
- `src/faultline/web/workspace.css`: isolated sage/graphite tokens, responsive layouts, drawer, focus and reduced motion.
- `src/faultline/web/workspace-graph.js`: bounded Cytoscape viewer with selection, relationships, source links, fit/zoom and accessible node list.
- `src/faultline/web/app.js`, `index.html`: routing, existing Investigation entry, separate demo context and versioned assets.
- `src/faultline/workspace.py`: authenticated read models, graph data and safe indexing retry.
- `src/faultline/github/onboarding.py`, `github/router.py`: verified GitHub authorization and live repository operations.
- `src/faultline/api.py`: workspace router registration.
- `src/faultline/webhooks/github.py`: retain HMAC/dedup, require previously authorized workspace connections, scope access revocation.
- `src/faultline/queue/job_queue.py`: atomic worker claim and preserve cancellation outcomes.
- `src/faultline/investigator/pr_investigator.py`: honest external static verdicts, source metadata and correct saved caller targets.
- Tests: `test_workspace.py`, `workspace_browser.cjs`, and updated GitHub/webhook/security expectations.

## API mapping

| Screen/action | Data source |
|---|---|
| User, workspace membership, CSRF | Existing `GET /api/v1/auth/me` |
| Logout | Existing `POST /api/v1/auth/logout` |
| Overview and repository coverage | `GET /api/v1/workspace/overview`, tenant-scoped SQLAlchemy records |
| Pull requests | `GET /api/v1/workspace/pull-requests` |
| Investigations and persisted evidence | `GET /api/v1/workspace/investigations[/{id}]` |
| Jobs and supported retry | `GET /api/v1/workspace/activity`, `POST /activity/{id}/retry` |
| Actual dependency nodes/edges | `GET /api/v1/workspace/repositories/{id}/graph` |
| Repository sync/index | Existing `POST /api/v1/github/repositories/{id}/sync` and `/index`; index now dispatches the worker |
| Install/authorize | `GET /api/v1/github/install/url`, `/authorize`, `/callback`, `/oauth/callback` |

Every workspace read requires Firebase server-session verification and tenant membership. Mutations require CSRF. Evidence exposes known fields rather than arbitrary job payloads. Graph queries scope nodes to tenant ID, repository and indexed immutable SHA, use bound parameters, and cap views at 150 nodes/400 edges (the UI requests 100). Lists show at most the latest 200 records; repository overview is capped at 500. Unavailable graph/service data returns an error, not invented zero counts.

## GitHub authorization and manual setup

Firebase GitHub sign-in is **not** App source authorization. The server uses a GitHub App user OAuth token to call `GET /user/installations` and `GET /user/installations/{id}/repositories`. It accepts only the configured App's installations and repositories with explicit GitHub admin permission. Installation ownership conflicts across workspaces are rejected. User access tokens remain server-side, in request memory only.

State is HMAC-signed, bound to the current Firebase user and workspace, and matched to an expiring HttpOnly SameSite=Lax browser cookie. Setup redirects' `installation_id` is ignored as an authorization claim. Unknown installations arriving via signed webhooks are acknowledged without implicitly creating or joining a workspace. After authorization, select a saved candidate and start its index. Changes to installation repository access may require authorization again.

The App owner must manually configure/verify in GitHub:

1. GitHub App OAuth callback: `https://<your-origin>/api/v1/github/oauth/callback` (local example: `http://localhost:8000/api/v1/github/oauth/callback`).
2. App Setup URL: `https://<your-origin>/api/v1/github/callback`, preserving GitHub's returned state.
3. Webhook URL: `https://<your-public-origin>/api/v1/webhooks/github`, matching secret and subscribed installation/repository/PR/check events. GitHub cannot deliver to plain localhost without an appropriate tunnel/deployment.
4. Appropriate Contents/Pull Requests/Metadata read and Checks write permissions, installation selection and App visibility. An owner-only App cannot be advertised as public developer onboarding.
5. Server-managed `FZ_GITHUB_APP_ID`, mounted private key through `FZ_GITHUB_APP_PRIVATE_KEY_PATH`, `FZ_GITHUB_CLIENT_ID`, `FZ_GITHUB_CLIENT_SECRET`, `FZ_GITHUB_WEBHOOK_SECRET`, allowed application origins, and existing Firebase Admin credentials. Use existing environment/managed secrets; never paste keys into browser files or commit them.

No environment file, credential mount, Firebase configuration, user data or Docker volume was changed for this integration. Existing Firebase production safety gates remain in force. Missing live GitHub credentials block onboarding/indexing instead of returning mock connections.

## Honest limitations

- Public/external GitHub onboarding, actual installation consent and real PR webhook → final Check publication were **not live-verified** during this implementation. Configuration presence is not a health or delivery check.
- External repository analysis is read-only Python AST/static graph analysis. It does not execute untrusted code. Its handler returns INCONCLUSIVE without approved execution evidence, including when static invariant references exist.
- Intermediate job stages and Check publication success are not separately persisted. The timeline shows only recorded investigation timestamps; a stored Check ID offers a link with an explicit publication-status caveat.
- The graph explorer exposes the current indexed snapshot and bounded neighborhoods. Historical snapshot selection and a dedicated focus-by-PR-symbol endpoint are not implemented. Saved investigation graphs are projections, not independent execution proof.
- Manual PR rerun is not exposed because a safe rerun/check deduplication endpoint is absent. New PR commits use the existing webhook path. Manual indexing and eligible indexing retries are supported.
- Notifications, billing controls, generated fixes, runtime coverage percentages and AI evidence explanations are not fabricated. Graph failure/empty indexing/authorization errors remain explicit.
- Existing historical report verdicts are preserved; evaluate their recorded evidence and scope. Newly analyzed external PRs use the corrected static-only semantics.

## Verification

Run the existing project checks with `python -m pytest -q`. Run browser checks with `node tests/workspace_browser.cjs` while the port 8000 application is running. The browser suite uses installed Playwright and Microsoft Edge. It intercepts explicit authenticated response fixtures **only inside its test page** and reads draft workspace assets from source; no fixture endpoint or mock authentication is added to the application.

`output/workspace-verification/browser-results.json` distinguishes fixture interactions from real unauthenticated server checks. `fixture-*.png` images are actual rendered UI with synthetic test responses, **not live connected repositories**. They cover 1440, 1024, 768 and 390px. `real-investigation-1440.png` shows the running controlled-demo page. JavaScript errors and unexpected demo API requests are asserted absent on workspace routes.

Separate backend tests cover tenant isolation, missing session/CSRF, signed-state/browser binding, admin-only repository authorization, installation ownership conflicts, graph bounds and safe unavailable states. A temporary uniquely named graph was created and removed in the running FalkorDB to verify the actual query, edges, neighborhood and tenant scope. No user repository graph was changed by that check.

The user's existing Firebase sign-in opened the real zero-repository workspace in the visible port 8000 browser. Login/logout provider flows were not retested end-to-end; the user's session was preserved.

### Final observed results

- Full Python suite: **153 passed**. JavaScript syntax checks and Docker production image build passed. Port 8000 liveness returned 200.
- Browser fixture journeys passed at all four widths with no JavaScript console errors or unexpected commerce-demo requests.
- In the user's actual signed-in browser, switching to the already-authorized Enosh2212 workspace displayed its real RiskLens repository and saved INCONCLUSIVE investigations. The recorded file/symbol inspector and source links opened correctly. Its actual FalkorDB snapshot returned **47 nodes and 57 relationships** in the new explorer. This verifies reading existing authorized data; it does not verify a new GitHub installation or a newly triggered PR-to-Check journey.
