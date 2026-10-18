# UI simplification verification

The landing page now has five sections: hero, process, payment proof, rationale, and closing action. The workspace uses investigation / focused evidence graph / empirical proof columns, with technical detail disclosed in tabs and expandable steps. The canvas hero illustrates a single change-to-verification journey.

Files changed: src/faultline/web/index.html, styles.css, app.js, hero_network.js; .dockerignore (exclude nested Python caches that prevented Docker builds); scripts/preview.py (local UI preview forwarding API requests to the existing backend).

Validation: 35 pytest tests passed. Live smoke tests passed across legacy workflows and all five Git changes, including payment and synthesized refund holdout; clean control stayed not_reproduced and uncovered remained inconclusive. Desktop and 390px mobile pages had no horizontal overflow. Payment and refund were also executed through browser controls. Backend source was unchanged. Model provider execution was not verified in this redesign; live checks used deterministic graph traversal, labeled in the UI.

Screenshots are in output/clean-landing.png, clean-workspace.png, clean-refund.png, clean-mobile-landing.png, and clean-mobile-workspace.png.

Preview: http://localhost:8001, or the rebuilt application at http://localhost:8000. Run python scripts/preview.py to restart the editing preview.

Added an in-product Terminal tab with real report tool results, revision execution observations, reproducible baseline/candidate commands (including generated ScenarioSpec JSON), a Run investigation action, pending/error states, and Copy log. It is an investigation execution console; arbitrary shell input is not implemented. Browser verification confirmed actual payment output and verdict from the terminal Run action.
