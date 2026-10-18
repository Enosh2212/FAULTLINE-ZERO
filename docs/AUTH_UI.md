# Authentication screens

## Entry points and design

- `/login` and `/register` share `src/faultline/web/auth.html`, `auth.css`, and `auth.js`.
- The public landing header links directly to both screens with **Sign in** and **Create account**. Hero demo CTAs remain accessible. The entry-point flow was verified with mouse/keyboard navigation and at 1440, 1050, 746, 390, and 320 pixel widths.
- The centered charcoal card uses the same system typography and mint accent as the product.
- `ascii_field.js` is the shared animated renderer for the landing hero and authentication background. `hero-ascii.js` mounts that renderer on the existing hero.
- Login/register transitions crossfade with a short vertical movement; buttons provide hover/press feedback. Reduced motion disables these effects and freezes the background. Background rendering pauses when the browser is hidden.
- The card's decorative lightning icon and email/password notice were removed as requested. Branding remains in the page header. No email/password form is presented.

## Provider and session integration

1. `GET /api/v1/auth/config` reports explicitly enabled providers and allowlisted public Firebase web configuration. It never returns service-account credentials, GitHub client secrets, or the server session signing key.
2. GitHub is primary; Google is secondary. Provider buttons explain unavailable sign-in when the environment is not configured. Demo/mock authentication is never presented as successful provider authentication.
3. A configured client loads the pinned official Firebase modular SDK (`12.19.0`), selects browser-session persistence, and uses `signInWithPopup`. It requests identity only; repository authorization remains a separate GitHub App action.
4. Popup blocking offers an explicit `signInWithRedirect` fallback. A subsequent `getRedirectResult` resumes the same server exchange.
5. The provider ID token is sent to the existing same-origin `POST /api/v1/auth/session`. The endpoint verifies it and creates the existing HttpOnly session cookie.
6. The UI verifies that `GET /api/v1/auth/me` returns the same Firebase identity before showing success or redirecting. ID tokens are not stored by this UI or written to logs. Firebase client sign-out clears the temporary client identity after exchange.
7. Success opens `/#saas`; `next` accepts only a fixed list of local application destinations. External redirect targets are ignored.

States include initialization, SDK loading, provider authentication, server verification, success, provider unavailable, cancelled/blocked popup, invalid credentials, and network failure. Duplicate provider attempts are disabled during an active flow.

## Configuration

The shipped local demo is unconfigured and cannot create real provider accounts yet. Set the following public browser options, alongside the existing private server Firebase configuration:

```text
FZ_FIREBASE_PROJECT_ID
FZ_FIREBASE_WEB_API_KEY
FZ_FIREBASE_AUTH_DOMAIN
FZ_FIREBASE_WEB_APP_ID
FZ_FIREBASE_GITHUB_ENABLED=true
FZ_FIREBASE_GOOGLE_ENABLED=false
FZ_AUTH_MOCK_ENABLED=false
```

Install the optional server verifier with `pip install '.[auth]'`. Docker supports `FZ_PYTHON_EXTRAS=auth` at build time. Server-side credentials must use the existing credentials path or application default credentials. Add the site's domain to Firebase's authorized domains and enable the selected providers in Firebase Console. Firebase OAuth redirect-domain setup is required for redirect fallback. Configure durable writable database storage for real server sessions; do not use the read-only demo container's default SQLite path for real accounts. Production requires HTTPS, secure cookies, a private session signing key, and the existing production settings checks.

The editing preview now supports `/login` and `/register` and forwards Cookie/Set-Cookie and API status codes. No session middleware or GitHub App authorization semantics were replaced.

## Availability

- Email/password sign-in is not implemented in this UI; configuration reports `email_password: false`.
- Terms and Privacy links open an honest unpublished-document notice. No legal agreement or policy was invented.
- No provider credentials were supplied or enabled during this work. Live GitHub/Google OAuth has not been verified.

## Verification and review artifacts

- `tests/test_auth_ui_config.py`: config allowlist, no server-secret disclosure, mock mode exclusion, missing SDK, missing configuration.
- Existing `tests/test_auth_security.py`: session/cookie authentication and security behavior.
- `output/auth-ui-evaluation.json`: browser checks for routes, keyboard interaction, background motion, mobile layout, provider failures, popup fallback, and verified-cookie-before-redirect behavior.
- Browser provider/session success and error paths use isolated intercepted fixtures. They do not claim successful live OAuth.
- Screenshots: `output/auth-sign-in-desktop.png`, `auth-register-desktop.png`, `auth-loading-desktop.png` (isolated loading-state fixture), and `auth-register-mobile.png`.

## Files changed

UI: `auth.html`, `auth.css`, `auth.js`, `ascii_field.js`, `hero-ascii.js`.

Integration: `src/faultline/auth/router.py`, `src/faultline/config.py`, `src/faultline/api.py`, `scripts/preview.py`, `Dockerfile`, `docker-compose.yml`, `pyproject.toml`, and `.env.example`.

Validation: `tests/test_auth_ui_config.py` and local browser artifacts in `output/`.

Final checks: 12 authentication/config/security tests passed; 26 auth browser checks passed; 15 existing project/landing UI checks passed. The shared hero background also passed motion, offscreen-pause, reduced-motion, and mobile checks. Docker build succeeded. Live provider sign-in remains unverified because this environment has no real provider configuration.
