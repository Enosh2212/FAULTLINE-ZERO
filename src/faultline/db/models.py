"""SQLAlchemy models for multi-tenant FAULTLINE ZERO SaaS platform."""
from __future__ import annotations

import datetime
import uuid
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="member")  # 'admin', 'member'
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    memberships: Mapped[List["Membership"]] = relationship(
        "Membership", back_populates="user", cascade="all, delete-orphan"
    )


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    billing_tier: Mapped[str] = mapped_column(String(50), default="free")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    memberships: Mapped[List["Membership"]] = relationship(
        "Membership", back_populates="organization", cascade="all, delete-orphan"
    )
    workspace_installations: Mapped[List["WorkspaceInstallation"]] = relationship(
        "WorkspaceInstallation", back_populates="organization", cascade="all, delete-orphan"
    )
    installations: Mapped[List["GitHubInstallation"]] = relationship(
        "GitHubInstallation", back_populates="organization", cascade="all, delete-orphan"
    )
    repositories: Mapped[List["Repository"]] = relationship(
        "Repository", back_populates="organization", cascade="all, delete-orphan"
    )
    jobs: Mapped[List["BackgroundJob"]] = relationship(
        "BackgroundJob", back_populates="organization", cascade="all, delete-orphan"
    )
    audit_events: Mapped[List["AuditEvent"]] = relationship(
        "AuditEvent", back_populates="organization", cascade="all, delete-orphan"
    )


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), default="member")  # 'owner', 'admin', 'member'
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship("User", back_populates="memberships")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="memberships")


class GitHubInstallation(Base):
    __tablename__ = "github_installations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # GitHub installation_id
    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="SET NULL"), index=True, nullable=True
    )
    account_login: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(50), default="Organization")
    permissions_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    installed_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    organization: Mapped[Optional["Organization"]] = relationship("Organization", back_populates="installations")
    workspace_installations: Mapped[List["WorkspaceInstallation"]] = relationship(
        "WorkspaceInstallation", back_populates="installation", cascade="all, delete-orphan"
    )
    repositories: Mapped[List["Repository"]] = relationship(
        "Repository", back_populates="installation"
    )


class WorkspaceInstallation(Base):
    __tablename__ = "workspace_installations"
    __table_args__ = (
        UniqueConstraint("organization_id", "installation_id", name="uq_workspace_installation"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    installation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("github_installations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    authorized_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    authorized_repositories_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="workspace_installations")
    installation: Mapped["GitHubInstallation"] = relationship("GitHubInstallation", back_populates="workspace_installations")
    authorized_by_user: Mapped[Optional["User"]] = relationship("User")


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("organization_id", "github_repo_id", name="uq_organization_github_repo"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    installation_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("github_installations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    github_repo_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)  # "owner/repo"
    is_private: Mapped[bool] = mapped_column(Boolean, default=True)
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    indexing_status: Mapped[str] = mapped_column(String(50), default="unindexed")
    indexed_commit_sha: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    indexed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    index_summary_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="repositories")
    installation: Mapped[Optional["GitHubInstallation"]] = relationship(
        "GitHubInstallation", back_populates="repositories"
    )
    pull_requests: Mapped[List["PullRequest"]] = relationship(
        "PullRequest", back_populates="repository", cascade="all, delete-orphan"
    )
    investigations: Mapped[List["Investigation"]] = relationship(
        "Investigation", back_populates="repository", cascade="all, delete-orphan"
    )


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    github_pr_number: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), default="")
    head_branch: Mapped[str] = mapped_column(String(255), default="")
    head_sha: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    base_branch: Mapped[str] = mapped_column(String(255), default="main")
    base_sha: Mapped[str] = mapped_column(String(40), default="")
    author_login: Mapped[str] = mapped_column(String(255), default="")
    state: Mapped[str] = mapped_column(String(50), default="open")  # 'open', 'closed', 'merged'
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    repository: Mapped["Repository"] = relationship("Repository", back_populates="pull_requests")
    investigations: Mapped[List["Investigation"]] = relationship(
        "Investigation", back_populates="pull_request", cascade="all, delete-orphan"
    )


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repositories.id", ondelete="CASCADE"), index=True, nullable=False
    )
    pull_request_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True, index=True
    )
    commit_sha: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # 'pending', 'running', 'completed', 'failed', 'cancelled'
    verdict: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # 'REPRODUCED', 'CLEAN', 'INCONCLUSIVE'
    confidence: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # 'HIGH', 'MEDIUM', 'LOW'
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_graph_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    check_run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    repository: Mapped["Repository"] = relationship("Repository", back_populates="investigations")
    pull_request: Mapped[Optional["PullRequest"]] = relationship(
        "PullRequest", back_populates="investigations"
    )


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    delivery_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    event_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="received"
    )  # 'received', 'processed', 'failed', 'ignored'
    processed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    repository_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    pull_request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    job_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="queued"
    )  # 'queued', 'running', 'completed', 'failed', 'cancelled'
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="jobs")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="audit_events"
    )


class RevokedSession(Base):
    __tablename__ = "revoked_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    revoked_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

