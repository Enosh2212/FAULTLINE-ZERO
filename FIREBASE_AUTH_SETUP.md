# Firebase authentication: faultime-66bce

The registered public Web App config is in `src/faultline/web/firebase-config.json`. The Web SDK loads from Firebase official CDN (12.19.0). Public Firebase config is application metadata. No Admin keys or OAuth secrets belong in this file.

## Backend setup required

Firebase Admin is now a normal installed dependency. The running backend currently has no usable Admin credentials; session creation returns 503. Client-side registration, verification emails and password reset can operate independently, but they do not grant a server session.

Prefer Application Default Credentials from a managed service identity / workload identity belonging to faultime-66bce. Give that backend identity Firebase Authentication Admin permissions (`roles/firebaseauth.admin`, or an appropriately scoped custom role permitting session-cookie creation and user lookup). A project ID alone is not authentication. ADC must support the Identity Toolkit session-cookie API. No private key needs to be pasted into chat.

For local certificate-based setup, obtain the credential privately through Firebase Console > Project settings > Service accounts, store it outside the repo, and restrict file access. Set FZ_FIREBASE_ADMIN_FILE to that absolute host path and run:

    docker compose -f docker-compose.yml -f docker-compose.firebase-admin.example.yml up -d --build api

The override mounts the file read-only at /run/secrets/firebase-admin.json; only the backend receives its path. For a non-container backend set FZ_FIREBASE_CREDENTIALS_PATH to the private file path, or use ADC. Never put credential contents into browser code, source control, logs, or chat. No service-account file was requested or created by this implementation.

Production must set FZ_ENV=production, FZ_AUTH_MOCK_ENABLED=false, FZ_SESSION_COOKIE_SECURE=true, FZ_AUTO_SEED=false, FZ_ALLOWED_ORIGINS to exact HTTPS frontend origins, and a random FZ_SESSION_SECRET_KEY of at least 32 characters (CSRF / GitHub state signing only). Existing GitHub App webhook configuration also requires a strong FZ_GITHUB_WEBHOOK_SECRET. Missing/invalid Admin credentials abort production startup. Development still serves the controlled demo, but never accepts mock identity tokens.

Docker uses a writable persistent auth_data volume for local users, memberships and logout revocations. Configure a backed-up relational database for production. Existing external FZ_DATABASE_URL overrides are respected; keep their data and migrate explicitly if changing an existing deployment.

## Firebase Console manual checks

Email/Password, Google and GitHub are enabled per your confirmation. Add localhost and your deployed domain to Authentication > Settings > Authorized domains. Check API-key restrictions allow Firebase Authentication from those origins. Configure verification/password-reset email templates, sender and action-link domains. Firebase-hosted action pages handle verification and password changes; the app offers resend and a verification check afterward.

Google requires a configured support email and OAuth consent settings. GitHub provider OAuth callback must be https://faultime-66bce.firebaseapp.com/__/auth/handler; its client secret stays in Firebase Console. This OAuth app is distinct from the GitHub App used for repository access. Do not put either GitHub OAuth secrets or GitHub App private keys in the browser.

## Session model and audit corrections

The previous custom HS256 session JWT and unsigned/mock Firebase fallbacks have been removed. Admin verifies ID tokens with revocation checks, requires email_verified and auth_time within five minutes, then creates a five-day Firebase session cookie. The SDK identity is kept in memory and signed out after exchange. Firebase cookies are HttpOnly, SameSite=Lax, Secure in production, host-only, and checked with verify_session_cookie(check_revoked=True) on protected requests. Disabled users and Firebase revocations fail closed.

Session exchange requires an allowed Origin plus a random pre-login double-submit nonce. Mutations including logout require a CSRF HMAC bound to the local user and SHA256 cookie fingerprint. Logout persists revocation of the current cookie and clears it; other devices remain signed in. Replaying the logged-out cookie fails. Firebase password-reset revocation is respected by Admin verification.

Existing memberships remain authoritative. New users receive private workspaces, never a shared default organization; requesting an unauthorized organization is rejected. /workspace is protected by the backend. The SaaS view also requires /auth/me. Tenant GitHub APIs retain membership checks. Production controlled-demo APIs require a Firebase session and CSRF for mutations; development demo access remains available. Hash routes and static HTML are not data security boundaries.

## Verification status

See output/firebase-auth-browser-results.json and AUTH_UI.md. Automated fixtures exercise UI success and failure paths, not live provider accounts. A successful real login, verified-email round trip, password-reset completion, Google/GitHub OAuth consent, protected server session and live logout still require backend credentials and a human-controlled account/mailbox. Do not describe these as live-verified until completed.
