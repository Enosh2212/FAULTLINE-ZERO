# Final focused UI/auth fixes

## Root cause and fix

The public header rendered unconditional Sign in/Create account links. It never initialized from `/api/v1/auth/me`. The existing Firebase ID-token exchange already verified the resulting server cookie, and the cookie was valid: the authenticated workspace worked while the public header still appeared signed out. This was a frontend identity-state problem, not missing cookie persistence.

`session-state.js` now reads the server-verified session with `credentials: include` and `cache: no-store`. Navigation starts neutral until verification completes. The public header and workspace share this state. Successful login signals other open tabs to reverify. Logout retains CSRF/revocation, removes private workspace DOM/state, updates other tabs, and returns to the public page. Page-hide/back-cache restoration clears private data and reverifies before restoring a workspace. No privileged tokens are placed in localStorage.

The only backend change is private response cache policy in the existing request middleware: `/workspace` and auth/workspace/GitHub private API responses use `Cache-Control: no-store, private` and vary by cookie/workspace. Session exchange, Admin verification, cookie flags, CSRF and revocation implementation are preserved. A single backend rebuild deployed this auth-related cache change; a later frontend-only image layer deployed the ELK cleanup correction without reinstalling backend dependencies.

## UI and graph

- Public navigation now contains the brand, How It Works and session-dependent controls. No functioning public Docs page existed, so Docs is omitted. Product navigation remains in the authenticated sidebar; commerce remains the separate demo.
- Landing capability copy now explains authorized GitHub/Python static analysis and bounded runtime verification. Hero artwork, dot typography, illustration and their animations were preserved.
- Six interactive workflow steps explicitly identify themselves as illustrative, not live status. Desktop uses horizontal cards/arrows; narrow screens use vertical steps. Clicking or keyboard-activating a step reveals its explanation.
- Existing Cytoscape and ELK now render rounded typed rectangles and directional arrowheads using ELK layered positions, left to right. Only actual returned edges are displayed. The initial view prioritizes a bounded neighborhood (the real RiskLens snapshot opened with 4 nodes/3 relationships rather than all 47 nodes).
- Selected nodes show full source, incoming/outgoing edges, test/invariant references and provenance. Related paths highlight progressively; unrelated nodes dim. Reduced motion skips animation. Empty/isolated results explain their limitations. Search/type filters preserve connected context within the loaded snapshot; view switching offers Impact or Repository Structure, with file-symbol collapse/expand, neighborhood expansion, fit and zoom.
- The duplicate empty-state Run Investigation control is hidden; the contextual demo command-bar control remains.

## Modified source files

- `src/faultline/web/index.html`
- `src/faultline/web/app.js`
- `src/faultline/web/auth.js`
- `src/faultline/web/workspace.js`
- `src/faultline/web/workspace.css`
- `src/faultline/web/workspace-graph.js`
- Added `src/faultline/web/session-state.js`
- Added `src/faultline/web/public-ui.js`
- Added `src/faultline/web/public-ui.css`
- `src/faultline/api.py` (private cache policy only)
- Added focused browser test `tests/final_ui_browser.cjs`.

## Verification actually performed

- **38 affected backend tests passed:** Firebase sessions, workspace tenant checks and GitHub webhook/security regressions. Existing session replay rejection, provider-boundary tests, CSRF and stale-event protection remained passing.
- Focused browser checks passed with **no JavaScript page errors**: neutral auth loading, header changes, refresh, logout/Back cleanup, graph selection, filters, empty/isolated states, fit/zoom, structure collapse and reduced motion. The synthetic response fixtures used for frontend edge cases are explicitly confined to the test browser; no fixture screenshots or production fixture endpoints were created.
- Real unauthenticated port-8000 checks confirmed `/workspace` redirects and private APIs deny access with private/no-store headers.
- In the user's actual signed-in browser: landing header recognized the existing session, refresh retained it, the real RiskLens graph rendered with ELK, selecting `process_features` showed the correct source line/incoming CALLS edge, and mobile workspace navigation opened correctly.
- **Real logout was performed.** Public controls changed to Sign In/Get Started; browser Back reached the login page instead of restoring the workspace. The user then signed in again; the authenticated landing header and refresh were reverified.
- Actual public workflow screenshots were captured at **1440px and 390px**, with no document overflow. Six step interactions and keyboard activation passed at both sizes.
- JavaScript syntax checks and the container build passed. No new dependencies/frameworks, Firebase/GitHub credential changes or volume deletion occurred. No webhook/indexing/investigation engine changes were made in this task.

## Actual screenshots

All files below capture the running UI, not mocked data or generated artwork:

- `output/final-ui/actual-signed-out-header-1440.png`
- `output/final-ui/actual-signed-in-header.png` (actual user browser viewport)
- `output/final-ui/actual-workflow-1440.png`
- `output/final-ui/actual-workflow-390.png`
- `output/final-ui/actual-risklens-directed-graph.png` (real repository)
- `output/final-ui/actual-mobile-public-navigation.png` (390px)
- `output/final-ui/actual-mobile-workspace-navigation.png` (actual narrow user browser)

Results: `output/final-ui/browser-results.json`; backend log: `output/final-ui-backend-tests.log`.

## Remaining limits

Snapshot selection currently exposes the current indexed commit only; the existing API does not support historical snapshot selection. Search applies to the loaded bounded graph; expansion can retrieve additional neighbors. A PR selector was optional and was not added without a supporting graph-focus contract. No fresh GitHub PR/webhook/Check was triggered during this focused UI task; existing automation regressions passed and its implementation was preserved.
