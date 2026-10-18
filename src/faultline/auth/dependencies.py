"""FastAPI dependency providers for authentication, RBAC, and CSRF protection."""
from __future__ import annotations

from typing import Optional, Tuple

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from faultline.auth.session import verify_csrf_token
from faultline.auth.firebase import verify_firebase_session, AuthConfigurationError
import hashlib
from faultline.config import get_settings
from faultline.db.models import Membership, Organization, Repository, RevokedSession, User
from faultline.db.session import get_db, seed_default_tenant


def _extract_token_from_request(request: Request) -> Optional[str]:
    settings = get_settings()
    # 1. Cookie
    cookie_token = request.cookies.get(settings.session_cookie_name)
    if cookie_token:
        request.state.token_source = "cookie"
        return cookie_token


    return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Validates session token and returns the authenticated User."""
    token = _extract_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = verify_firebase_session(token)
    except AuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Server authentication is not configured") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    uid = payload.get("uid") or payload.get("sub")
    user = db.query(User).filter_by(firebase_uid=uid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti = hashlib.sha256(token.encode()).hexdigest()
    if jti:
        revoked = db.query(RevokedSession).filter_by(jti=jti).first()
        if revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Attach session metadata to request state
    request.state.user = user
    request.state.session_jti = jti
    request.state.session_exp = payload.get("exp")
    request.state.session_org_id = None
    request.state.session_role = None
    return user


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Returns authenticated User if valid session exists; otherwise None."""
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None


def verify_csrf(
    request: Request,
    user: User = Depends(get_current_user),
    x_csrf_token: Optional[str] = Header(None, alias="X-CSRF-Token"),
) -> None:
    """Enforces CSRF token validation on mutating HTTP methods when session cookie is used."""
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        token_source = getattr(request.state, "token_source", None)
        # CSRF is mandatory if authenticated via cookie
        if token_source == "cookie":
            jti = getattr(request.state, "session_jti", None)
            if not jti or not x_csrf_token or not verify_csrf_token(x_csrf_token, user.id, jti):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="CSRF token missing or invalid",
                )


def get_authorized_org(
    request: Request,
    org_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Tuple[User, Organization, Membership]:
    """Ensures the authenticated user has access to the requested organization."""
    target_org_id = (
        org_id
        or request.headers.get("X-Organization-Id")
        or request.query_params.get("org_id")
        or getattr(request.state, "session_org_id", None)
    )

    if target_org_id:
        membership = (
            db.query(Membership)
            .filter_by(user_id=user.id, organization_id=target_org_id)
            .first()
        )
    else:
        membership = db.query(Membership).filter_by(user_id=user.id).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: User is not a member of this organization",
        )

    organization = db.query(Organization).filter_by(id=membership.organization_id).first()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    return user, organization, membership


def get_authorized_repo(
    repo_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Tuple[User, Organization, Repository]:
    """Ensures the repository exists and user belongs to its organization."""
    repository = db.query(Repository).filter_by(id=repo_id).first()
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{repo_id}' not found",
        )

    membership = (
        db.query(Membership)
        .filter_by(user_id=user.id, organization_id=repository.organization_id)
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: User does not belong to the repository's organization",
        )

    return user, repository.organization, repository
