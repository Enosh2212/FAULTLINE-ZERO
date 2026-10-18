"""Database session management and engine configuration."""
from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from faultline.db.models import Base, Membership, Organization, User

DEFAULT_SQLITE_URL = "sqlite:///./faultline_zero.db"


def get_database_url() -> str:
    url = os.getenv("FZ_DATABASE_URL", DEFAULT_SQLITE_URL).strip()
    # Normalize postgres:// -> postgresql:// for SQLAlchemy compatibility
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    return url


def create_app_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_database_url()
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        engine = create_engine(url, connect_args=connect_args, echo=False)

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        return engine

    return create_engine(url, pool_pre_ping=True, echo=False)


# Global default engine and session maker
_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionFactory
    if _engine is None:
        _engine = create_app_engine()
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        get_engine()
    assert _SessionFactory is not None
    return _SessionFactory


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db(engine: Engine | None = None) -> None:
    """Initialize database tables and create initial default tenant if empty."""
    target_engine = engine or get_engine()
    Base.metadata.create_all(bind=target_engine)

    # Lightweight schema migration for SQLite: add any missing columns to repositories
    try:
        with target_engine.connect() as conn:
            existing_cols = {
                row[1] for row in conn.exec_driver_sql("PRAGMA table_info(repositories)").fetchall()
            }
            if existing_cols:
                if "indexing_status" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE repositories ADD COLUMN indexing_status VARCHAR(50) DEFAULT 'unindexed'")
                if "indexed_commit_sha" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE repositories ADD COLUMN indexed_commit_sha VARCHAR(40)")
                if "indexed_at" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE repositories ADD COLUMN indexed_at DATETIME")
                if "index_summary_json" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE repositories ADD COLUMN index_summary_json TEXT")
                conn.commit()

            # Backfill workspace_installations from existing github_installations where organization_id is set
            try:
                conn.exec_driver_sql("""
                    INSERT OR IGNORE INTO workspace_installations (id, organization_id, installation_id, created_at, updated_at)
                    SELECT lower(hex(randomblob(16))), organization_id, id, installed_at, updated_at
                    FROM github_installations
                    WHERE organization_id IS NOT NULL
                """)
                conn.commit()
            except Exception:
                pass
    except Exception:
        pass


def seed_default_tenant(session: Session) -> tuple[User, Organization] | None:
    """Ensures a default developer user and organization exist for local evaluation. Disabled in production."""
    from faultline.config import get_settings
    settings = get_settings()
    if settings.is_production:
        return None

    default_org = session.query(Organization).filter_by(slug="default-org").first()
    if not default_org:
        default_org = Organization(
            id="org-default-001",
            name="Default Organization",
            slug="default-org",
            billing_tier="enterprise",
        )
        session.add(default_org)
        session.flush()

    default_user = session.query(User).filter_by(firebase_uid="dev-user-001").first()
    if not default_user:
        default_user = User(
            id="usr-default-001",
            firebase_uid="dev-user-001",
            email="developer@faultlinezero.local",
            display_name="Lead Engineer",
            role="admin",
        )
        session.add(default_user)
        session.flush()

    membership = (
        session.query(Membership)
        .filter_by(user_id=default_user.id, organization_id=default_org.id)
        .first()
    )
    if not membership:
        membership = Membership(
            id="mem-default-001",
            user_id=default_user.id,
            organization_id=default_org.id,
            role="owner",
        )
        session.add(membership)
        session.flush()

    session.commit()
    return default_user, default_org
