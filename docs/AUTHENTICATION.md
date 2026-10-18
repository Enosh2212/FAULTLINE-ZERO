# FAULTLINE ZERO — Authentication & Authorization Architecture

## Overview
This document outlines the authentication and repository authorization model for FAULTLINE ZERO, clearly distinguishing between the **Hackathon Demonstration Scope** and the **Production Multi-Tenant Architecture**.

---

## 1. Hackathon Demonstration Scope vs. Production

| Capability | Hackathon Demonstration Scope | Production Architecture |
|---|---|---|
| **User Authentication** | Open Local Session (Localhost) | Google OAuth 2.0 & GitHub OAuth 2.0 |
| **Repository Access** | Pre-Indexed Synthetic Commerce Repository (`demo-repository`) | GitHub App Installation Tokens |
| **Session State** | In-Memory / Local Storage | Cryptographically Signed JWT Cookies (`HttpOnly`, `SameSite=Lax`) |
| **Role-Based Access** | Single Developer / Evaluator Mode | Multi-Tenant Organization & Team RBAC |
| **Secret Management** | Local Environment File (`.env`) | HashiCorp Vault / AWS Secrets Manager |

> [!NOTE]  
> In compliance with engineering integrity guidelines, the current running deployment does not simulate a fake GitHub OAuth pop-up or fabricate non-existent user directories. The current dashboard clearly labels repositories as local verified fixtures and provides full architectural designs for enterprise authentication below.

---

## 2. Production Multi-Tenant OAuth 2.0 Flow

In a production SaaS deployment, user login and repository authorization follow standard OAuth 2.0 Authorization Code Grant flows with PKCE.

### 2.1 Google Workspace SSO
1. Developer initiates login via `GET /auth/google/login`.
2. Server redirects to `accounts.google.com/o/oauth2/v2/auth` requesting scopes `openid`, `email`, `profile`.
3. Callback `GET /auth/google/callback` exchanges the authorization code for an ID token, validates the domain against enterprise SSO policy, and issues a session JWT.

### 2.2 GitHub Organization Installation Flow
1. Engineering admin clicks "Install FAULTLINE ZERO" on GitHub Marketplace.
2. GitHub redirects to `github.com/apps/faultline-zero/installations/new`.
3. Admin selects repositories (All repositories or specific repositories).
4. GitHub webhook dispatches `installation.created` with `installation_id`.
5. FAULTLINE ZERO server generates a GitHub App JWT (signed with the app's RS256 private key) and exchanges it for a short-lived **Installation Access Token** (valid 1 hour).
6. The installation access token is scoped strictly to the selected repositories.

---

## 3. JWT Session & Security Policy

- **Token Algorithm**: RS256 (Asymmetric key pair).
- **Expiration**: 15 minutes access token, 7 days refresh token stored in encrypted Redis store.
- **Cookie Security**:
  ```http
  Set-Cookie: flz_session=eyJhbGci...; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=900
  ```
- **CSRF Protection**: Double Submit Cookie pattern or custom header validation (`X-Requested-With: FaultlineZero`).
