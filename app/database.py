"""
Database layer.

Uses SQLAlchemy over SQLite for Phase 1. The schema is deliberately simple
and flat so it can migrate to PostgreSQL later with minimal changes (see
README "Future Roadmap"). Service lists are stored as JSON text since
SQLite has no native array type.

Duplicate-processing protection comes from a UNIQUE constraint on
reddit_post_id: attempting to insert a post that already exists is treated
as a normal, expected "already processed" case, not an error.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()

DEFAULT_LEAD_STATUS = "NEW"

#: Primary pipeline stages a counsellor moves a lead through.
PIPELINE_STATUSES: List[str] = [
    "NEW",
    "CONTACTED",
    "RESPONDED",
    "COUNSELLING",
    "APPLICATION",
    "CONVERTED",
]

#: Terminal/secondary states, tracked separately from the primary pipeline.
SECONDARY_STATUSES: List[str] = ["NO_RESPONSE", "NOT_QUALIFIED", "CLOSED"]

ALL_LEAD_STATUSES: List[str] = PIPELINE_STATUSES + SECONDARY_STATUSES


class DatabaseError(RuntimeError):
    """Raised when a database operation fails unrecoverably."""


class Lead(Base):
    """A single processed Reddit post and its lead-analysis results."""

    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)

    reddit_post_id = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, nullable=False)
    subreddit = Column(String, nullable=False)
    title = Column(Text, nullable=False)
    post_url = Column(String, nullable=False)
    post_text = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)

    destination = Column(String, nullable=True)
    course = Column(String, nullable=True)
    intent = Column(String, nullable=True)
    service_needed = Column(Text, nullable=True)  # JSON-encoded list[str]

    ai_is_lead = Column(Boolean, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    ai_reason = Column(Text, nullable=True)

    pre_filter_score = Column(Integer, nullable=True)
    lead_score = Column(Integer, nullable=True)
    lead_classification = Column(String, nullable=True)

    lead_status = Column(String, nullable=False, default=DEFAULT_LEAD_STATUS)
    assigned_counsellor = Column(String, nullable=True)

    processed_at = Column(DateTime, nullable=False)


class LeadNote(Base):
    """
    A counsellor's note attached to a lead. Additive, for the web product
    layer — notes are never written by the intelligence engine itself.
    """

    __tablename__ = "lead_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, nullable=False, index=True)
    note_text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)


class ActivityLog(Base):
    """
    A minimal, real activity feed (per the product brief: "add a minimal
    activity table rather than generating fake activity"). Every event
    recorded here corresponds to something that actually happened —
    scans, validations, status changes, notes.
    """

    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    lead_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False)


class ScanRun(Base):
    """
    A record of one Reddit scan (real Apify retrieval + filter + classify
    + score + save), for the Scan page's "Recent Scans" section. Purely
    additive persistence for the product layer — the scan pipeline itself
    still lives in app/scan_service.py, unchanged in what it calls.
    """

    __tablename__ = "scan_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String, nullable=False)  # running | done | error
    sources = Column(Text, nullable=False)  # JSON list of subreddit names
    post_limit = Column(Integer, nullable=False)
    discovered = Column(Integer, nullable=True)
    filtered = Column(Integer, nullable=True)
    analyzed = Column(Integer, nullable=True)
    hot = Column(Integer, nullable=True)
    warm = Column(Integer, nullable=True)
    cold = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)


class Database:
    """Thin repository wrapping SQLAlchemy session/engine management."""

    def __init__(self, database_path: str) -> None:
        parent_dir = os.path.dirname(database_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{database_path}", future=True)
        self._SessionLocal = sessionmaker(bind=self._engine, expire_on_commit=False)

    def init_db(self) -> None:
        """Create tables if they do not already exist. Safe to call repeatedly."""
        try:
            Base.metadata.create_all(self._engine)
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to initialize database: {exc}") from exc

    @contextmanager
    def _session(self) -> Iterator[Session]:
        session = self._SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def is_duplicate(self, reddit_post_id: str) -> bool:
        """Return True if this Reddit post has already been processed."""
        try:
            with self._session() as session:
                existing = (
                    session.query(Lead.id)
                    .filter(Lead.reddit_post_id == reddit_post_id)
                    .first()
                )
                return existing is not None
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to check for duplicate post: {exc}") from exc

    def save_lead(
        self,
        *,
        reddit_post_id: str,
        username: str,
        subreddit: str,
        title: str,
        post_url: str,
        post_text: str,
        created_at: datetime,
        destination: Optional[str] = None,
        course: Optional[str] = None,
        intent: Optional[str] = None,
        service_needed: Optional[List[str]] = None,
        ai_is_lead: Optional[bool] = None,
        ai_confidence: Optional[float] = None,
        ai_reason: Optional[str] = None,
        pre_filter_score: Optional[int] = None,
        lead_score: Optional[int] = None,
        lead_classification: Optional[str] = None,
    ) -> bool:
        """
        Persist a processed post. Returns True if a new row was inserted,
        False if it was already present (duplicate — no-op).
        """
        lead = Lead(
            reddit_post_id=reddit_post_id,
            username=username,
            subreddit=subreddit,
            title=title,
            post_url=post_url,
            post_text=post_text,
            created_at=created_at,
            destination=destination,
            course=course,
            intent=intent,
            service_needed=json.dumps(service_needed or []),
            ai_is_lead=ai_is_lead,
            ai_confidence=ai_confidence,
            ai_reason=ai_reason,
            pre_filter_score=pre_filter_score,
            lead_score=lead_score,
            lead_classification=lead_classification,
            lead_status=DEFAULT_LEAD_STATUS,
            assigned_counsellor=None,
            processed_at=datetime.now(timezone.utc),
        )
        try:
            with self._session() as session:
                session.add(lead)
            return True
        except IntegrityError:
            logger.info("Post %s already exists — skipping duplicate insert.", reddit_post_id)
            return False
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to save lead {reddit_post_id}: {exc}") from exc

    # -----------------------------------------------------------------
    # Web product-layer additions below. These are purely additive reads
    # and small, explicit mutations (status changes, notes, activity) on
    # top of the schema above — the intelligence engine's own read/write
    # path (`is_duplicate`, `save_lead`) is untouched.
    # -----------------------------------------------------------------

    @staticmethod
    def _lead_to_dict(lead: "Lead") -> dict:
        return {
            "id": lead.id,
            "reddit_post_id": lead.reddit_post_id,
            "username": lead.username,
            "subreddit": lead.subreddit,
            "title": lead.title,
            "post_url": lead.post_url,
            "post_text": lead.post_text,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
            "destination": lead.destination,
            "course": lead.course,
            "intent": lead.intent,
            "service_needed": json.loads(lead.service_needed) if lead.service_needed else [],
            "ai_is_lead": bool(lead.ai_is_lead) if lead.ai_is_lead is not None else None,
            "ai_confidence": lead.ai_confidence,
            "ai_reason": lead.ai_reason,
            "pre_filter_score": lead.pre_filter_score,
            "lead_score": lead.lead_score,
            "lead_classification": lead.lead_classification,
            "lead_status": lead.lead_status,
            "assigned_counsellor": lead.assigned_counsellor,
            "processed_at": lead.processed_at.isoformat() if lead.processed_at else None,
        }

    def list_leads(
        self,
        *,
        classification: Optional[str] = None,
        status: Optional[str] = None,
        subreddit: Optional[str] = None,
        destination: Optional[str] = None,
        course: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Return {"items": [...], "total": N} of leads matching the filters,
        newest first."""
        try:
            with self._session() as session:
                query = session.query(Lead)
                if classification:
                    query = query.filter(Lead.lead_classification == classification.upper())
                if status:
                    query = query.filter(Lead.lead_status == status.upper())
                if subreddit:
                    query = query.filter(Lead.subreddit == subreddit)
                if destination:
                    query = query.filter(Lead.destination == destination)
                if course:
                    query = query.filter(Lead.course == course)
                if search:
                    like = f"%{search}%"
                    query = query.filter(Lead.title.ilike(like))
                total = query.count()
                rows = (
                    query.order_by(Lead.processed_at.desc())
                    .offset(max(0, offset))
                    .limit(max(1, min(limit, 200)))
                    .all()
                )
                return {"items": [self._lead_to_dict(r) for r in rows], "total": total}
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to list leads: {exc}") from exc

    def get_lead(self, lead_id: int) -> Optional[dict]:
        try:
            with self._session() as session:
                lead = session.query(Lead).filter(Lead.id == lead_id).first()
                return self._lead_to_dict(lead) if lead else None
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to fetch lead {lead_id}: {exc}") from exc

    def update_lead_status(self, lead_id: int, new_status: str) -> Optional[dict]:
        """Move a lead to a new pipeline/terminal status. Returns the
        updated lead dict, or None if the lead doesn't exist."""
        new_status = new_status.upper()
        if new_status not in ALL_LEAD_STATUSES:
            raise DatabaseError(
                f"Invalid lead status {new_status!r}; must be one of {ALL_LEAD_STATUSES}."
            )
        try:
            with self._session() as session:
                lead = session.query(Lead).filter(Lead.id == lead_id).first()
                if not lead:
                    return None
                old_status = lead.lead_status
                lead.lead_status = new_status
                session.add(
                    ActivityLog(
                        event_type="status_changed",
                        message=f'Lead moved from {old_status} to {new_status}: "{lead.title[:80]}"',
                        lead_id=lead.id,
                        created_at=datetime.now(timezone.utc),
                    )
                )
                session.flush()
                result = self._lead_to_dict(lead)
                return result
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to update status for lead {lead_id}: {exc}") from exc

    def add_note(self, lead_id: int, note_text: str) -> dict:
        try:
            with self._session() as session:
                lead = session.query(Lead).filter(Lead.id == lead_id).first()
                if not lead:
                    raise DatabaseError(f"Lead {lead_id} does not exist.")
                note = LeadNote(
                    lead_id=lead_id, note_text=note_text, created_at=datetime.now(timezone.utc)
                )
                session.add(note)
                session.add(
                    ActivityLog(
                        event_type="note_added",
                        message=f'Note added to "{lead.title[:80]}"',
                        lead_id=lead_id,
                        created_at=datetime.now(timezone.utc),
                    )
                )
                session.flush()
                return {
                    "id": note.id,
                    "lead_id": note.lead_id,
                    "note_text": note.note_text,
                    "created_at": note.created_at.isoformat(),
                }
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to add note to lead {lead_id}: {exc}") from exc

    def list_notes(self, lead_id: int) -> List[dict]:
        try:
            with self._session() as session:
                rows = (
                    session.query(LeadNote)
                    .filter(LeadNote.lead_id == lead_id)
                    .order_by(LeadNote.created_at.desc())
                    .all()
                )
                return [
                    {
                        "id": n.id,
                        "lead_id": n.lead_id,
                        "note_text": n.note_text,
                        "created_at": n.created_at.isoformat(),
                    }
                    for n in rows
                ]
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to list notes for lead {lead_id}: {exc}") from exc

    def log_activity(
        self, event_type: str, message: str, lead_id: Optional[int] = None
    ) -> None:
        try:
            with self._session() as session:
                session.add(
                    ActivityLog(
                        event_type=event_type,
                        message=message,
                        lead_id=lead_id,
                        created_at=datetime.now(timezone.utc),
                    )
                )
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to log activity: {exc}") from exc

    def list_activity(self, limit: int = 50) -> List[dict]:
        try:
            with self._session() as session:
                rows = (
                    session.query(ActivityLog)
                    .order_by(ActivityLog.created_at.desc())
                    .limit(max(1, min(limit, 200)))
                    .all()
                )
                return [
                    {
                        "id": a.id,
                        "event_type": a.event_type,
                        "message": a.message,
                        "lead_id": a.lead_id,
                        "created_at": a.created_at.isoformat(),
                    }
                    for a in rows
                ]
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to list activity: {exc}") from exc

    def get_dashboard_stats(self) -> dict:
        try:
            with self._session() as session:
                total = session.query(Lead).count()
                hot = session.query(Lead).filter(Lead.lead_classification == "HOT").count()
                warm = session.query(Lead).filter(Lead.lead_classification == "WARM").count()
                cold = session.query(Lead).filter(Lead.lead_classification == "COLD").count()
                today_start = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                new_today = (
                    session.query(Lead).filter(Lead.processed_at >= today_start).count()
                )
                return {
                    "total_leads": total,
                    "hot": hot,
                    "warm": warm,
                    "cold": cold,
                    "new_today": new_today,
                }
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to compute dashboard stats: {exc}") from exc

    def get_pipeline(self) -> dict:
        """Leads grouped by lead_status, for the Kanban board. Each lead
        is a compact summary (not the full record)."""
        try:
            with self._session() as session:
                rows = session.query(Lead).order_by(Lead.processed_at.desc()).all()
                board: dict = {status: [] for status in ALL_LEAD_STATUSES}
                for lead in rows:
                    status = lead.lead_status if lead.lead_status in board else DEFAULT_LEAD_STATUS
                    board[status].append(
                        {
                            "id": lead.id,
                            "title": lead.title,
                            "subreddit": lead.subreddit,
                            "lead_score": lead.lead_score,
                            "lead_classification": lead.lead_classification,
                            "destination": lead.destination,
                            "course": lead.course,
                        }
                    )
                return board
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to build pipeline board: {exc}") from exc

    def get_analytics(self) -> dict:
        """Real aggregates only — no fabricated historical trends. Any
        dimension with zero data comes back as an empty dict/list, which
        the frontend renders as an explicit empty state."""
        try:
            with self._session() as session:
                rows = session.query(Lead).all()

                def _count_by(key_fn):
                    counts: dict = {}
                    for lead in rows:
                        key = key_fn(lead)
                        if key:
                            counts[key] = counts.get(key, 0) + 1
                    return counts

                service_counts: dict = {}
                for lead in rows:
                    for service in json.loads(lead.service_needed) if lead.service_needed else []:
                        service_counts[service] = service_counts.get(service, 0) + 1

                return {
                    "total_leads": len(rows),
                    "priority_distribution": _count_by(lambda l: l.lead_classification),
                    "pipeline_distribution": _count_by(lambda l: l.lead_status),
                    "subreddit_distribution": _count_by(lambda l: l.subreddit),
                    "destination_distribution": _count_by(lambda l: l.destination),
                    "course_distribution": _count_by(lambda l: l.course),
                    "service_demand": service_counts,
                }
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to compute analytics: {exc}") from exc

    # -- Scan run persistence (Recent Scans) -----------------------------

    def create_scan_run(self, *, sources: List[str], post_limit: int) -> int:
        try:
            with self._session() as session:
                run = ScanRun(
                    status="running",
                    sources=json.dumps(sources),
                    post_limit=post_limit,
                    started_at=datetime.now(timezone.utc),
                )
                session.add(run)
                session.flush()
                return run.id
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to create scan run: {exc}") from exc

    def update_scan_run(self, scan_run_id: int, **fields) -> None:
        """Patch a scan run with any subset of its columns (discovered,
        filtered, analyzed, hot, warm, cold, status, error, finished_at)."""
        try:
            with self._session() as session:
                run = session.query(ScanRun).filter(ScanRun.id == scan_run_id).first()
                if not run:
                    return
                for key, value in fields.items():
                    if hasattr(run, key):
                        setattr(run, key, value)
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to update scan run {scan_run_id}: {exc}") from exc

    def list_scan_runs(self, limit: int = 10) -> List[dict]:
        try:
            with self._session() as session:
                rows = (
                    session.query(ScanRun)
                    .order_by(ScanRun.started_at.desc())
                    .limit(max(1, min(limit, 50)))
                    .all()
                )
                return [
                    {
                        "id": r.id,
                        "status": r.status,
                        "sources": json.loads(r.sources) if r.sources else [],
                        "post_limit": r.post_limit,
                        "discovered": r.discovered,
                        "filtered": r.filtered,
                        "analyzed": r.analyzed,
                        "hot": r.hot,
                        "warm": r.warm,
                        "cold": r.cold,
                        "error": r.error,
                        "started_at": r.started_at.isoformat() if r.started_at else None,
                        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                    }
                    for r in rows
                ]
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to list scan runs: {exc}") from exc
