"""FastAPI router for Firebase session authentication and user profile endpoints."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

import datetime
import hashlib
import hmac
import secrets
import time
import json
from pathlib import Path
from faultline.auth.dependencies import get_current_user, verify_csrf
from faultline.auth.firebase import (verify_firebase_id_token, create_firebase_session, admin_ready, AuthConfigurationError)
from faultline.auth.session import (
    generate_csrf_token,
)
from faultline.config import get_settings
from faultline.db.models import AuditEvent, Membership, Organization, RevokedSession, User, utcnow
from faultline.db.session import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_token: str
    organization_slug: Optional[str] = None


class UserProfileSchema(BaseModel):
    id: str
    firebase_uid: str
    email: str
    display_name: str
    avatar_url: Optional[str] = None
    role: str


class OrgSummarySchema(BaseModel):
    id: str
    name: str
    slug: str
    billing_tier: str
    role: str


class SessionResponse(BaseModel):
    user: UserProfileSchema
    organization: Optional[OrgSummarySchema]
    csrf_token: str
    role: str


class MeResponse(BaseModel):
    user: UserProfileSchema
    current_organization: Optional[OrgSummarySchema]
    organizations: List[OrgSummarySchema]
    csrf_token: str


@router.get("/config")
def public_auth_config(response: Response):
    """Publish only Firebase's browser configuration, never server credentials."""
    settings = get_settings()
    firebase = {
        **json.loads((Path(__file__).parents[1] / "web/firebase-config.json").read_text()),
        "apiKey": settings.firebase_web_api_key,
        "authDomain": settings.firebase_auth_domain,
        "projectId": settings.firebase_project_id,
        "appId": settings.firebase_web_app_id,
    }
    configured = bool(
        all(firebase.values())
        and not settings.auth_mock_enabled
        
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "configured": configured,
        "firebase": firebase if configured else None,
        "providers": {
            "github": configured and settings.firebase_github_enabled,
            "google": configured and settings.firebase_google_enabled,
        },
        "email_password": configured,
        "server_session_ready": admin_ready(),
    }



@router.get("/csrf")
def login_csrf(response: Response):
    nonce = secrets.token_urlsafe(32)
    settings = get_settings()
    response.set_cookie("fz_login_csrf", nonce, max_age=600, httponly=True,
                        secure=settings.session_cookie_secure, samesite="strict", path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"csrf_token": nonce}


def require_login_csrf(request):
    settings = get_settings()
    origin = request.headers.get("origin")
    if not origin or origin not in settings.allowed_origins:
        raise HTTPException(403, "Sign-in origin is not allowed")
    cookie = request.cookies.get("fz_login_csrf", "")
    header = request.headers.get("x-csrf-token", "")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(403, "Sign-in CSRF token missing or invalid")

@router.post("/session", response_model=SessionResponse)
def create_session(
    body: SessionCreateRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Exchanges a Firebase ID token for an HttpOnly session cookie and returns user profile + CSRF token.
    Automatically provisions new users into their default organization.
    """
    settings = get_settings()
    require_login_csrf(request)
    try:
        claims = verify_firebase_id_token(body.id_token)
        if not claims.get("uid"):
            raise ValueError("Missing identity")
        auth_age = time.time() - claims.get("auth_time", 0)
        if not 0 <= auth_age <= 300:
            raise HTTPException(401, "Please sign in again before creating a session")
        if not claims.get("email_verified"):
            raise HTTPException(403, "Verify your email before signing in")
        token = create_firebase_session(body.id_token)
    except HTTPException:
        raise
    except AuthConfigurationError as exc:
        raise HTTPException(503, "Server authentication is not configured") from exc
    except Exception as exc:
        raise HTTPException(401, "Authentication could not be verified") from exc

    uid = claims["uid"]
    email = claims.get("email", "")
    name = claims.get("name", "")
    picture = claims.get("picture")

    # Find or provision user
    user = db.query(User).filter_by(firebase_uid=uid).first()
    if not user:
        user = User(
            firebase_uid=uid,
            email=email,
            display_name=name,
            avatar_url=picture,
            role="member",
        )
        db.add(user)
        db.flush()

    # Never auto-join a shared tenant or trust an organization supplied by a client.
    membership = db.query(Membership).filter_by(user_id=user.id).first()
    if body.organization_slug:
        requested = db.query(Organization).filter_by(slug=body.organization_slug).first()
        membership = (db.query(Membership).filter_by(user_id=user.id, organization_id=requested.id).first()
                      if requested else None)
        if not membership:
            raise HTTPException(403, "Organization access denied")
    if membership:
        org = db.query(Organization).filter_by(id=membership.organization_id).one()
    else:
        org = Organization(name=f"{name or 'My'} workspace", slug=f"workspace-{user.id}")
        db.add(org)
        db.flush()
        membership = Membership(user_id=user.id, organization_id=org.id, role="owner")
        db.add(membership)
        db.flush()
    user.email, user.display_name, user.avatar_url = email, name, picture

    # Audit login
    audit = AuditEvent(
        organization_id=org.id,
        user_id=user.id,
        action="user.authenticated",
        resource_type="User",
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    db.commit()

    # Issue session token and CSRF token
    jti = hashlib.sha256(token.encode()).hexdigest()
    csrf_token = generate_csrf_token(user.id, jti)

    # Set secure HttpOnly session cookie
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=5 * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )

    response.delete_cookie("fz_login_csrf", path="/")
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(
        user=UserProfileSchema(
            id=user.id,
            firebase_uid=user.firebase_uid,
            email=user.email,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            role=user.role,
        ),
        organization=OrgSummarySchema(
            id=org.id,
            name=org.name,
            slug=org.slug,
            billing_tier=org.billing_tier,
            role=membership.role,
        )
        if org
        else None,
        csrf_token=csrf_token,
        role=membership.role,
    )


@router.post("/logout", dependencies=[Depends(verify_csrf)])
def logout(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Invalidates the session token server-side and clears the cookie."""
    settings = get_settings()
    jti = getattr(request.state, "session_jti", None)
    if jti:
        exp_ts = getattr(request.state, "session_exp", None)
        expires_at = (
            datetime.datetime.fromtimestamp(exp_ts, datetime.timezone.utc)
            if exp_ts
            else utcnow() + datetime.timedelta(days=14)
        )
        existing = db.query(RevokedSession).filter_by(jti=jti).first()
        if not existing:
            revocation = RevokedSession(
                jti=jti,
                user_id=user.id,
                expires_at=expires_at,
            )
            db.add(revocation)
            db.commit()

    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"status": "logged_out"}


@router.get("/me", response_model=MeResponse)
def get_me(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns the authenticated user, active organization, memberships, and a fresh CSRF token."""
    memberships = db.query(Membership).filter_by(user_id=user.id).all()
    org_summaries = []
    current_org_summary = None
    active_org_id = getattr(request.state, "session_org_id", None)

    for m in memberships:
        org = db.query(Organization).filter_by(id=m.organization_id).first()
        if org:
            summary = OrgSummarySchema(
                id=org.id,
                name=org.name,
                slug=org.slug,
                billing_tier=org.billing_tier,
                role=m.role,
            )
            org_summaries.append(summary)
            if active_org_id and org.id == active_org_id:
                current_org_summary = summary

    if not current_org_summary and org_summaries:
        current_org_summary = org_summaries[0]

    jti = getattr(request.state, "session_jti", "fresh")
    csrf_token = generate_csrf_token(user.id, jti)

    return MeResponse(
        user=UserProfileSchema(
            id=user.id,
            firebase_uid=user.firebase_uid,
            email=user.email,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            role=user.role,
        ),
        current_organization=current_org_summary,
        organizations=org_summaries,
        csrf_token=csrf_token,
    )
