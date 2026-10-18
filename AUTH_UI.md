# Auth UI verification

Premium emerald/charcoal card, shared animated ASCII backdrop, navigation and mobile layout are preserved. Email/password, email verification/resend/check, password reset, Google and GitHub now use Firebase Web SDK. Client tokens stay in memory; Firebase Admin owns the server cookie.

Backend: 43 focused tests passed covering identity/session boundaries, CSRF, current-cookie logout and replay rejection, private workspace provisioning, tenant isolation, production configuration/startup failure, Admin revocation flags and protected page redirects.

Browser: 10 checks passed (output/firebase-auth-browser-results.json). Real SDK initialized using faultime-66bce; live Firebase rejected an invalid email/password login. Registration/mobile/forgot-password UI verified. Injected SDK and HTTP fixtures tested email verification gating, reset dispatch, verified session exchange, client sign-out, Google/GitHub session paths, and unavailable Admin failure. These fixtures are not evidence of live authentication success.

Not live-verified: successful registration, mailbox delivery and verification link, password reset completion, Google/GitHub OAuth completion, authenticated server session and logout. The backend currently lacks Admin credentials. See FIREBASE_AUTH_SETUP.md for secure setup and manual account checks.

Screenshots: output/firebase-login-desktop.png and output/firebase-register-mobile.png.

After configuring Admin, manually register using a mailbox you control, verify the email, sign in, confirm /workspace and /api/v1/auth/me, log out and confirm access is denied. Complete password reset and each provider login separately. Check another device remains signed in after current-session logout and that Firebase-disabled accounts are rejected.
