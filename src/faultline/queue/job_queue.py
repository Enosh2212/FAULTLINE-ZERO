"""Asynchronous job queue and worker dispatcher for multi-tenant background tasks."""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, Optional

from sqlalchemy.orm import Session

from faultline.db.models import BackgroundJob, PullRequest, utcnow
from faultline.db.session import get_session_factory

logger = logging.getLogger("faultline.queue")

# Global registry of job handlers
_JOB_HANDLERS: Dict[str, Callable[[BackgroundJob, Session], Any]] = {}


def register_job_handler(job_type: str):
    """Decorator to register a handler for a job type."""

    def decorator(fn: Callable[[BackgroundJob, Session], Any]):
        _JOB_HANDLERS[job_type] = fn
        return fn

    return decorator


class JobQueue:
    """Manages background jobs with idempotency, concurrency throttling, and stale cancellation."""

    @staticmethod
    def enqueue(
        db: Session,
        organization_id: str,
        job_type: str,
        idempotency_key: str,
        payload: Dict[str, Any],
        repository_id: str | None = None,
        pull_request_id: str | None = None,
        max_attempts: int = 3,
    ) -> BackgroundJob:
        """Enqueues a background job or returns existing matching job if idempotent."""
        existing = (
            db.query(BackgroundJob).filter_by(idempotency_key=idempotency_key).first()
        )
        if existing:
            logger.info("Job with idempotency key %s already exists (status=%s)", idempotency_key, existing.status)
            return existing

        job = BackgroundJob(
            organization_id=organization_id,
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            job_type=job_type,
            status="queued",
            idempotency_key=idempotency_key,
            payload_json=json.dumps(payload),
            max_attempts=max_attempts,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def cancel_pr_jobs(db: Session, pull_request_id: str) -> int:
        """Cancels older pending or in-flight jobs for a PR when a newer commit arrives."""
        active_jobs = (
            db.query(BackgroundJob)
            .filter(
                BackgroundJob.pull_request_id == pull_request_id,
                BackgroundJob.status.in_(["queued", "running"]),
            )
            .all()
        )
        count = len(active_jobs)
        for j in active_jobs:
            j.status = "cancelled"
            j.error_message = "Superseded by newer commit on PR (stale cancellation)"
            j.updated_at = utcnow()
        if count > 0:
            db.commit()
            logger.info("Cancelled %d stale background jobs for PR %s", count, pull_request_id)
        return count

    @staticmethod
    def recover_abandoned_jobs(db: Session) -> int:
        """Recovers jobs that were left in 'running' state due to an unexpected worker/server crash."""
        stuck_jobs = db.query(BackgroundJob).filter_by(status="running").all()
        recovered = 0
        for j in stuck_jobs:
            if j.attempts >= j.max_attempts:
                j.status = "failed"
                j.error_message = "Exhausted retry limit after unrecovered process crash"
            else:
                j.status = "queued"
                j.error_message = "Recovered after unhandled server restart; eligible for retry"
            j.updated_at = utcnow()
            recovered += 1
        if recovered > 0:
            db.commit()
            logger.info("Recovered %d abandoned running background jobs after restart", recovered)
        return recovered

    session_factory_override: Optional[sessionmaker[Session]] = None
    MAX_CONCURRENT_PER_TENANT: int = 5

    @classmethod
    def process_job_now(cls, job_id: str, db: Session | None = None) -> bool:
        """Executes a single job synchronously within a clean database session."""
        close_on_exit = False
        if db is None:
            factory = cls.session_factory_override or get_session_factory()
            db = factory()
            close_on_exit = True

        job: Optional[BackgroundJob] = None
        try:
            job = db.query(BackgroundJob).filter_by(id=job_id).first()
            if not job:
                logger.error("Job %s not found", job_id)
                return False

            if job.status in {"completed", "cancelled"}:
                logger.info("Job %s already in terminal state %s", job_id, job.status)
                return True

            # Claim once across concurrent retry requests/background tasks.
            claimed = db.query(BackgroundJob).filter(
                BackgroundJob.id == job_id,
                BackgroundJob.status.in_(["queued", "failed"]),
                BackgroundJob.attempts < BackgroundJob.max_attempts,
            ).update({BackgroundJob.status: "running", BackgroundJob.attempts: BackgroundJob.attempts + 1,
                      BackgroundJob.updated_at: utcnow()}, synchronize_session=False)
            db.commit()
            if not claimed:
                return False
            db.refresh(job)

            handler = _JOB_HANDLERS.get(job.job_type)
            if not handler:
                raise ValueError(f"No handler registered for job type '{job.job_type}'")

            handler(job, db)

            db.refresh(job)
            if job.status == "cancelled":
                return True
            job.status = "completed"
            job.updated_at = utcnow()
            db.commit()
            return True
        except Exception as exc:
            attempts = job.attempts if job else 1
            logger.exception("Job %s failed on attempt %d: %s", job_id, attempts, exc)
            db.rollback()
            try:
                # Re-query in fresh state to record failure
                failed_job = db.query(BackgroundJob).filter_by(id=job_id).first()
                if failed_job:
                    failed_job.error_message = str(exc)
                    if failed_job.attempts >= failed_job.max_attempts:
                        failed_job.status = "failed"
                    else:
                        failed_job.status = "queued"  # Eligible for retry
                    failed_job.updated_at = utcnow()
                    db.commit()
            except Exception:
                pass
            return False
        finally:
            if close_on_exit:
                db.close()
