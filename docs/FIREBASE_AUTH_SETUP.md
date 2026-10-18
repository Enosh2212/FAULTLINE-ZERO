# FAULTLINE ZERO — Firebase Authentication & Secure Session Setup

## Overview
FAULTLINE ZERO has provider-based browser screens at `/login` and `/register`, connected to Firebase Authentication and the existing server-side session cookies (`HttpOnly`, `SameSite=Lax`). GitHub is the primary provider and Google is optional. Email/password is not implemented in these screens. See [Authentication screens](AUTH_UI.md) for browser configuration, actual availability, and validation limits.

---

## 1. Firebase Console Configuration

1. Create or open a project in the [Firebase Console](https://console.firebase.google.com/).
2. Enable Authentication providers:
   - **Google Workspace / Google Sign-In**
   - **GitHub OAuth Sign-In**
   - Email / Password is not used by the current browser UI.
3. Under **Project Settings → Service Accounts**, click **Generate new private key** to download your service account JSON file.
4. Place the credentials on your secure host (e.g., `/etc/faultline/firebase-service-account.json`).

---

## 2. Server Environment Configuration

Configure the following variables in `.env`:

```env
# Firebase Configuration
FZ_FIREBASE_PROJECT_ID=your-firebase-project-id
FZ_FIREBASE_CREDENTIALS_PATH=/etc/faultline/firebase-service-account.json

# Session Cookie Security
FZ_SESSION_SECRET_KEY=generate_a_cryptographically_secure_random_64_byte_key
FZ_SESSION_COOKIE_NAME=__session
FZ_SESSION_COOKIE_SECURE=true  # Set to true in production HTTPS
FZ_AUTH_MOCK_ENABLED=false     # Set to false in production to enforce real Firebase ID tokens
```

---

## 3. Session Exchange Protocol

1. Client signs in with Firebase JS SDK:
   ```javascript
   const userCredential = await signInWithPopup(auth, googleProvider);
   const idToken = await userCredential.user.getIdToken();
   ```
2. Client sends token to FAULTLINE ZERO server:
   ```http
   POST /api/v1/auth/session HTTP/1.1
   Content-Type: application/json

   {
     "id_token": "eyJhbGciOiJSUzI1NiIs..."
   }
   ```
3. Server verifies token via `firebase_admin.auth.verify_id_token(id_token)`:
   - Extracts `uid`, `email`, `name`, `picture`.
   - Provisions or retrieves `User` in database.
   - Issues cryptographically signed session cookie:
     ```http
     Set-Cookie: __session=eyJhbGciOiJIUzI1Ni...; Path=/; HttpOnly; SameSite=Lax; Secure; Max-Age=1209600
     ```
   - Returns JSON body with user profile and signed `csrf_token`.
4. Subsequent mutating requests (`POST`, `PUT`, `DELETE`, `PATCH`) must include:
   ```http
   X-CSRF-Token: <csrf_token>
   ```

---

## 4. Local Developer & Testing Mode

When `FZ_AUTH_MOCK_ENABLED=true` (the default in testing and local development), mock tokens formatted as `mock:<uid>:<email>:<name>` are accepted without needing external Google Cloud credentials. This guarantees that automated CI test suites and offline evaluators can run cleanly out of the box.
