"""GitHub App client with JWT generation, Installation Token exchange, and Checks API."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx

from faultline.config import get_settings

logger = logging.getLogger("faultline.github.client")


def generate_install_state(
    organization_id: str,
    user_id: str,
    secret_key: str | None = None,
    expires_in: int = 1800,  # 30 minutes
    flow: str = "install",
    prev_repo_ids: list[int] | None = None,
) -> str:
    """Generates an HMAC-signed state parameter with onboarding intent to prevent CSRF during GitHub App installation."""
    settings = get_settings()
    secret = (secret_key or settings.session_secret_key).encode("utf-8")
    now = int(time.time())
    nonce = uuid.uuid4().hex[:16]

    payload = {
        "org_id": organization_id,
        "user_id": user_id,
        "flow": flow,
        "prev_repo_ids": prev_repo_ids or [],
        "nonce": nonce,
        "exp": now + expires_in,
    }
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        .decode("utf-8")
        .rstrip("=")
    )
    sig = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_install_state(
    state: str,
    secret_key: str | None = None,
) -> Dict[str, str]:
    """Verifies HMAC signature and expiration on state token; returns payload dict."""
    if not state or "." not in state:
        raise ValueError("Invalid installation state token format")

    settings = get_settings()
    secret = (secret_key or settings.session_secret_key).encode("utf-8")
    payload_b64, sig = state.split(".", 1)

    expected_sig = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("Installation state signature mismatch")

    padding = 4 - (len(payload_b64) % 4)
    if padding and padding < 4:
        payload_b64 += "=" * padding

    data = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8"))
    if int(time.time()) > int(data.get("exp", 0)):
        raise ValueError("Installation state expired")

    return data


class GitHubAppClient:
    """GitHub API client supporting both live GitHub App authentication and mock testing mode."""

    def __init__(
        self,
        app_id: int | None = None,
        private_key: str | None = None,
        mock_mode: bool = False,
    ):
        settings = get_settings()
        self.app_id = app_id or settings.github_app_id
        self.private_key = private_key or settings.github_app_private_key
        if not self.private_key and settings.github_app_private_key_path:
            try:
                with open(settings.github_app_private_key_path, "r", encoding="utf-8") as f:
                    self.private_key = f.read().strip()
            except Exception as e:
                logger.warning("Could not read GitHub App private key: %s", e)

        # Automatically use mock mode if credentials are not configured or requested
        self.mock_mode = mock_mode or (not self.app_id or not self.private_key)
        self._mock_check_run_seq = 1000
        self._mock_check_runs: Dict[int, Dict[str, Any]] = {}
        self._mock_comments: List[Dict[str, Any]] = []
        self._installation_tokens: Dict[int, Dict[str, Any]] = {}

    def generate_app_jwt(self) -> str:
        """Generates an RS256 JWT for GitHub App authentication."""
        if self.mock_mode or not self.private_key or not self.app_id:
            return "mock-github-app-jwt"

        try:
            import jwt

            now = int(time.time())
            payload = {
                "iat": now - 60,
                "exp": now + (10 * 60),  # Max 10 minutes
                "iss": str(self.app_id),
            }
            return jwt.encode(payload, self.private_key, algorithm="RS256")
        except Exception as e:
            logger.error("Failed to generate GitHub App JWT: %s", e)
            if self.mock_mode:
                return "mock-github-app-jwt"
            raise

    def get_installation_access_token(self, installation_id: int) -> str:
        """Exchanges App JWT for a short-lived installation access token with auto-refresh."""
        if self.mock_mode:
            return f"ghs_mock_installation_token_{installation_id}"

        # Return cached token if still valid for at least 5 minutes
        now = time.time()
        cached = self._installation_tokens.get(installation_id)
        if cached and cached.get("expires_at", 0) > now + 300:
            return cached["token"]

        jwt_token = self.generate_app_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            token = data["token"]

            # Parse expires_at (ISO 8601 string)
            exp_ts = now + 3600
            expires_at_str = data.get("expires_at")
            if expires_at_str:
                try:
                    import datetime
                    exp_dt = datetime.datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                    exp_ts = exp_dt.timestamp()
                except Exception:
                    pass

            self._installation_tokens[installation_id] = {
                "token": token,
                "expires_at": exp_ts,
            }
            return token

    def list_installation_repositories(self, installation_id: int) -> List[Dict[str, Any]]:
        """Lists repositories accessible to this installation (supports pagination)."""
        if self.mock_mode:
            return [
                {
                    "id": 901001,
                    "name": "payment-gateway",
                    "full_name": "acme-corp/payment-gateway",
                    "private": True,
                    "default_branch": "main",
                    "html_url": "https://github.com/acme-corp/payment-gateway",
                },
                {
                    "id": 901002,
                    "name": "inventory-service",
                    "full_name": "acme-corp/inventory-service",
                    "private": True,
                    "default_branch": "main",
                    "html_url": "https://github.com/acme-corp/inventory-service",
                },
            ]

        token = self.get_installation_access_token(installation_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        all_repos: List[Dict[str, Any]] = []
        page = 1
        with httpx.Client(timeout=15.0) as client:
            while True:
                url = f"https://api.github.com/installation/repositories?per_page=100&page={page}"
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                repos = data.get("repositories", [])
                all_repos.extend(repos)
                if len(repos) < 100 or len(all_repos) >= data.get("total_count", 0):
                    break
                page += 1
        return all_repos

    def get_pr_files(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> List[Dict[str, Any]]:
        """Fetches list of changed files for a pull request."""
        if self.mock_mode:
            return [
                {
                    "filename": "src/payment/gateway.py",
                    "status": "modified",
                    "additions": 14,
                    "deletions": 5,
                    "changes": 19,
                    "patch": "@@ -45,5 +45,14 @@ def process_transaction(user_id, amount):\n+    # updated retry logic",
                }
            ]

        token = self.get_installation_access_token(installation_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files?per_page=100"
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def get_file_content(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> str | None:
        """Fetches file content at a specific commit SHA without cloning."""
        if self.mock_mode:
            return "def process_transaction(user_id, amount):\n    return {'status': 'processed'}\n"

        token = self.get_installation_access_token(installation_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}"
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            if data.get("encoding") == "base64" and data.get("content"):
                decoded = base64.b64decode(data["content"]).decode("utf-8-sig", errors="replace")
                return decoded.lstrip("\ufeff")
            return None

    def get_repository_tree(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        ref: str,
        recursive: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fetches the complete Git tree for a commit or branch ref without cloning.
        Returns list of tree objects with path, mode, type ('blob'/'tree'), sha, size.
        """
        if self.mock_mode:
            return [
                {"path": "src/payment/gateway.py", "type": "blob", "sha": "mockblob01", "size": 1200},
                {"path": "src/payment/processor.py", "type": "blob", "sha": "mockblob02", "size": 950},
                {"path": "src/inventory/stock.py", "type": "blob", "sha": "mockblob03", "size": 800},
                {"path": "tests/test_gateway.py", "type": "blob", "sha": "mockblob04", "size": 1500},
                {"path": "README.md", "type": "blob", "sha": "mockblob05", "size": 400},
            ]

        token = self.get_installation_access_token(installation_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        rec_param = "1" if recursive else "0"
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}?recursive={rec_param}"
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()
            return data.get("tree", [])

    def get_blob(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        blob_sha: str,
    ) -> str | None:
        """Fetches raw blob text by blob SHA."""
        if self.mock_mode:
            if "gateway" in blob_sha or blob_sha == "mockblob01":
                return (
                    "def process_transaction(user_id, amount):\n"
                    "    '''Process transaction with ledger update.'''\n"
                    "    return {'status': 'processed', 'amount': amount}\n"
                )
            if "processor" in blob_sha or blob_sha == "mockblob02":
                return (
                    "from src.payment.gateway import process_transaction\n\n"
                    "def execute_charge(account, cost):\n"
                    "    return process_transaction(account, cost)\n"
                )
            if "stock" in blob_sha or blob_sha == "mockblob03":
                return (
                    "def check_inventory(sku, count):\n"
                    "    return count >= 0\n"
                )
            if "test_gateway" in blob_sha or blob_sha == "mockblob04":
                return (
                    "from src.payment.gateway import process_transaction\n\n"
                    "def test_process_transaction():\n"
                    "    res = process_transaction('u1', 100)\n"
                    "    assert res['status'] == 'processed'\n"
                )
            return "Mock content"

        token = self.get_installation_access_token(installation_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.raw+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url = f"https://api.github.com/repos/{owner}/{repo}/git/blobs/{blob_sha}"
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.text.lstrip("\ufeff")

    def create_check_run(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        name: str,
        head_sha: str,
        status: str = "queued",
        details_url: str | None = None,
        external_id: str | None = None,
    ) -> Dict[str, Any]:
        """Creates a Check Run on the commit SHA."""
        if self.mock_mode:
            self._mock_check_run_seq += 1
            check_run_id = self._mock_check_run_seq
            record = {
                "id": check_run_id,
                "name": name,
                "head_sha": head_sha,
                "status": status,
                "conclusion": None,
                "details_url": details_url or "http://localhost:8000",
                "external_id": external_id or "",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            self._mock_check_runs[check_run_id] = record
            return record

        token = self.get_installation_access_token(installation_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url = f"https://api.github.com/repos/{owner}/{repo}/check-runs"
        payload = {
            "name": name,
            "head_sha": head_sha,
            "status": status,
        }
        if details_url:
            payload["details_url"] = details_url
        if external_id:
            payload["external_id"] = external_id

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    def update_check_run(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        check_run_id: int,
        status: str = "completed",
        conclusion: str | None = None,  # "success", "failure", "neutral", "action_required"
        title: str | None = None,
        summary: str | None = None,
        text: str | None = None,
        annotations: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        """Updates an existing Check Run with conclusion and evidence markdown output."""
        if self.mock_mode:
            record = self._mock_check_runs.get(check_run_id, {"id": check_run_id})
            record["status"] = status
            record["conclusion"] = conclusion
            output = {}
            if title:
                output["title"] = title
            if summary:
                output["summary"] = summary
            if text:
                output["text"] = text
            if annotations:
                output["annotations"] = annotations
            record["output"] = output
            record["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._mock_check_runs[check_run_id] = record
            return record

        token = self.get_installation_access_token(installation_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url = f"https://api.github.com/repos/{owner}/{repo}/check-runs/{check_run_id}"
        payload: Dict[str, Any] = {"status": status}
        if conclusion:
            payload["conclusion"] = conclusion

        output: Dict[str, Any] = {}
        if title:
            output["title"] = title
        if summary:
            output["summary"] = summary
        if text:
            output["text"] = text
        if annotations:
            output["annotations"] = annotations

        if output:
            payload["output"] = output

        with httpx.Client(timeout=10.0) as client:
            resp = client.patch(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    def create_pr_comment(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
    ) -> Dict[str, Any]:
        """Posts an evidence markdown comment to the PR thread."""
        if self.mock_mode:
            comment = {
                "id": len(self._mock_comments) + 1,
                "pr_number": pr_number,
                "body": body,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            self._mock_comments.append(comment)
            return comment

        token = self.get_installation_access_token(installation_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, headers=headers, json={"body": body})
            resp.raise_for_status()
            return resp.json()


_global_github_client: GitHubAppClient | None = None


def get_github_client() -> GitHubAppClient:
    global _global_github_client
    if _global_github_client is None:
        _global_github_client = GitHubAppClient()
    return _global_github_client
