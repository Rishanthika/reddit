"""
FastAPI backend for the FutureGrad Reddit Lead Intelligence web product.

This is the product layer's HTTP surface. It reads from and writes to the
SAME SQLite database as the CLI (`python -m app.main`) via `Database`, and
triggers scans/validations via `app/scan_service.py`, which in turn reuses
the unmodified intelligence engine (`reddit_client.py`, `filters.py`,
`ai_classifier.py`, `lead_scoring.py`). No retrieval/filtering/
classification/scoring logic lives in this file.

Run with:

    uvicorn app.api:app --reload --port 8000

Never exposes APIFY_API_TOKEN or OPENAI_API_KEY to any response — see
`/api/settings` below.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import scan_service
from app.config import ConfigError, load_settings
from app.database import ALL_LEAD_STATUSES, Database, DatabaseError

logger = logging.getLogger(__name__)

app = FastAPI(title="FutureGrad Reddit Lead Intelligence API")

# Local-first: the Next.js dev server runs on a different port, so CORS
# needs to allow it. This is a localhost-only internal tool, not a public
# deployment, so a permissive local origin list is appropriate here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_settings():
    try:
        return load_settings()
    except ConfigError as exc:
        raise HTTPException(status_code=500, detail=f"Configuration error: {exc}") from exc


def _get_database() -> Database:
    settings = _get_settings()
    database = Database(settings.database_path)
    database.init_db()
    return database


class StatusUpdate(BaseModel):
    status: str


class NoteCreate(BaseModel):
    text: str


class ScanRequest(BaseModel):
    post_limit: Optional[int] = None


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/dashboard")
def dashboard():
    try:
        return _get_database().get_dashboard_stats()
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/leads")
def list_leads(
    classification: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    subreddit: Optional[str] = Query(None),
    destination: Optional[str] = Query(None),
    course: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    try:
        return _get_database().list_leads(
            classification=classification,
            status=status,
            subreddit=subreddit,
            destination=destination,
            course=course,
            search=search,
            limit=limit,
            offset=offset,
        )
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/leads/{lead_id}")
def get_lead(lead_id: int):
    database = _get_database()
    try:
        lead = database.get_lead(lead_id)
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found.")
    try:
        lead["notes"] = database.list_notes(lead_id)
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return lead


@app.patch("/api/leads/{lead_id}/status")
def update_lead_status(lead_id: int, body: StatusUpdate):
    database = _get_database()
    try:
        updated = database.update_lead_status(lead_id, body.status)
    except DatabaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Lead not found.")
    return updated


@app.get("/api/leads/{lead_id}/notes")
def list_notes(lead_id: int):
    try:
        return _get_database().list_notes(lead_id)
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/leads/{lead_id}/notes")
def add_note(lead_id: int, body: NoteCreate):
    try:
        return _get_database().add_note(lead_id, body.text)
    except DatabaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/pipeline")
def pipeline():
    try:
        return {
            "statuses": ALL_LEAD_STATUSES,
            "board": _get_database().get_pipeline(),
        }
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/analytics")
def analytics():
    try:
        return _get_database().get_analytics()
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/activity")
def activity(limit: int = Query(50, ge=1, le=200)):
    try:
        return _get_database().list_activity(limit=limit)
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/settings")
def settings_status():
    """Connector/environment status only. Never returns actual secrets."""
    try:
        settings = _get_settings()
    except HTTPException:
        return {
            "reddit_connector": "disconnected",
            "ai_provider": "unknown",
            "database": "unknown",
            "environment": "local",
        }
    return {
        "reddit_connector": "connected" if settings.apify_api_token else "disconnected",
        "ai_provider": settings.ai_provider,
        "database": "connected",
        "environment": "local",
        "subreddits": settings.subreddits,
        "post_limit": settings.post_limit,
        "classifier_validation_limit": settings.classifier_validation_limit,
    }


@app.post("/api/scan")
def start_scan(body: ScanRequest = ScanRequest()):
    settings = _get_settings()
    scan_id = scan_service.start_scan(settings, post_limit=body.post_limit)
    if scan_id is None:
        raise HTTPException(status_code=409, detail="A scan is already running.")
    return {"started": True}


@app.get("/api/scan/status")
def scan_status():
    return scan_service.get_scan_state()


@app.get("/api/scan/recent")
def recent_scans(limit: int = Query(10, ge=1, le=50)):
    try:
        return _get_database().list_scan_runs(limit=limit)
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/scan/limits")
def scan_limits():
    return {"allowed": list(scan_service.ALLOWED_POST_LIMITS)}


@app.post("/api/validation")
def start_validation():
    settings = _get_settings()
    started = scan_service.start_validation(settings)
    if not started:
        raise HTTPException(status_code=409, detail="A validation run is already in progress.")
    return {"started": True}


@app.get("/api/validation/status")
def validation_status():
    return scan_service.get_validation_state()
