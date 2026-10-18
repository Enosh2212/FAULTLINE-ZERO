# FAULTLINE ZERO — GitHub App Production Setup & Configuration

This guide provides step-by-step instructions for registering and deploying the FAULTLINE ZERO GitHub App.

---

## 1. Registering the GitHub App

1. Navigate to **GitHub Settings → Developer Settings → GitHub Apps → New GitHub App**.
2. Set the application details:
   - **App Name**: `FAULTLINE ZERO — Pre-Merge Regression Gate`
   - **Homepage URL**: `https://faultlinezero.io` (or your staging domain)
   - **Callback URL**: `https://<YOUR_API_DOMAIN>/api/v1/github/callback`
   - **Setup URL (optional)**: `https://<YOUR_API_DOMAIN>/#saas`
   - **Webhook URL**: `https://<YOUR_API_DOMAIN>/api/v1/webhooks/github`
   - **Webhook Secret**: Generate a cryptographically random 32-byte string (`openssl rand -hex 32`) and save it.

---

## 2. Least-Privilege Permissions Matrix

To adhere to strict principle of least privilege, configure **ONLY** the following scopes:

| Permission Category | Scope | Justification |
|---|---|---|
| **Repository Permissions: Pull Requests** | **Read & Write** | Read PR metadata/diffs and publish evidence breakdown comments |
| **Repository Permissions: Checks** | **Read & Write** | Create `in_progress` Check Runs and update them with `failure` / `success` conclusions and markdown summaries |
| **Repository Permissions: Contents** | **Read-only** | Clone repository files for static AST analysis |
| **Repository Permissions: Metadata** | **Read-only** | Standard read-only access to commit SHAs and repository properties |
| **Organization Permissions** | **No Access** | Not required |
| **Account Permissions** | **No Access** | Not required |

---

## 3. Subscribed Webhook Events

Under **Subscribe to events**, select only:
- [x] **Pull request** (`opened`, `synchronize`, `reopened`, `closed`)
- [x] **Check suite** (`rerequested`)
- [x] **Check run** (`rerequested`)
- [x] **Installation** (`created`, `deleted`, `suspend`, `unsuspend`)
- [x] **Installation target** (`renamed`)

---

## 4. Private Key Generation & Environment Variables

1. Under **Private keys**, click **Generate a private key**. Download the `.pem` file.
2. Configure the following environment variables in your server's `.env` file:

```env
# GitHub App Configuration
FZ_GITHUB_APP_ID=123456
FZ_GITHUB_APP_PRIVATE_KEY_PATH=/etc/faultline/github-app-private-key.pem
# OR provide base64/PEM directly in string:
# FZ_GITHUB_APP_PRIVATE_KEY="<YOUR_BASE64_OR_PEM_CONTENT>"
FZ_GITHUB_WEBHOOK_SECRET=your_generated_32_byte_webhook_secret
FZ_GITHUB_APP_SLUG=faultline-zero-regression-gate
```

---

## 5. Verifying the Connection

1. On the FAULTLINE ZERO dashboard, navigate to the **GitHub SaaS** tab.
2. Click **Install GitHub App**. You will be redirected to GitHub with a signed HMAC `state` token.
3. Select your target repositories on GitHub.
4. After approval, GitHub redirects back to `/api/v1/github/callback?installation_id=...&state=...`.
5. The dashboard will automatically reflect the installation and display your synchronized repositories.
