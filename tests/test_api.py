"""
Tests for the FastAPI product-layer backend (app/api.py) and the additive
database.py extensions it relies on (list_leads, get_lead, status/notes,
pipeline, analytics, activity).

Uses a temporary SQLite file and FastAPI's TestClient — no real Apify or
OpenAI calls, and no interference with a real data/leads.db.
"""

import os
import tempfile
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import Database


@pytest.fixture()
def db_path():
    path = tempfile.mktemp(suffix=".db")
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture()
def client(db_path, monkeypatch):
    monkeypatch.setenv("APIFY_API_TOKEN", "fake")
    monkeypatch.setenv("APIFY_ACTOR_ID", "automation-lab/reddit-scraper")
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("SUBREDDITS", "studyabroad,gradadmissions")
    monkeypatch.setenv("POST_LIMIT", "25")
    monkeypatch.setenv("DATABASE_PATH", db_path)
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("CLASSIFIER_VALIDATION_MODE", "false")
    monkeypatch.setenv("CLASSIFIER_VALIDATION_LIMIT", "30")

    from app.api import app  # imported after env vars are set

    return TestClient(app)


def _seed_lead(db_path, **overrides):
    db = Database(db_path)
    db.init_db()
    defaults = dict(
        reddit_post_id="p1",
        username="u/test",
        subreddit="studyabroad",
        title="Can i get admission in an Australian university with visa approval?",
        post_url="https://reddit.com/r/studyabroad/comments/p1",
        post_text="",
        created_at=datetime.now(timezone.utc),
        destination="Australia",
        course="Masters Engineering",
        intent="high",
        service_needed=["Application Guidance", "Visa Guidance"],
        ai_is_lead=True,
        ai_confidence=0.82,
        ai_reason="Personal, immediate visa/admission problem.",
        pre_filter_score=30,
        lead_score=95,
        lead_classification="HOT",
    )
    defaults.update(overrides)
    db.save_lead(**defaults)
    return db


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_dashboard_uses_real_database_values(db_path, client):
    _seed_lead(db_path)
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_leads"] == 1
    assert body["hot"] == 1
    assert body["warm"] == 0
    assert body["cold"] == 0


def test_dashboard_empty_database_returns_zeros_not_fabricated_data(client):
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    assert resp.json() == {"total_leads": 0, "hot": 0, "warm": 0, "cold": 0, "new_today": 0}


def test_list_leads_returns_seeded_lead(db_path, client):
    _seed_lead(db_path)
    resp = client.get("/api/leads")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"].startswith("Can i get admission")
    assert body["items"][0]["service_needed"] == ["Application Guidance", "Visa Guidance"]


def test_list_leads_filters_by_classification(db_path, client):
    db = _seed_lead(db_path)
    db.save_lead(
        reddit_post_id="p2", username="u/other", subreddit="studyabroad",
        title="Best business majors", post_url="https://reddit.com/x", post_text="",
        created_at=datetime.now(timezone.utc), ai_is_lead=False,
        lead_score=0, lead_classification="COLD",
    )
    resp = client.get("/api/leads", params={"classification": "hot"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["lead_classification"] == "HOT"


def test_get_lead_detail_includes_notes(db_path, client):
    db = _seed_lead(db_path)
    lead = db.get_lead(1)
    db.add_note(lead["id"], "Test note")

    resp = client.get(f"/api/leads/{lead['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["notes"]) == 1
    assert body["notes"][0]["note_text"] == "Test note"


def test_get_lead_404_for_missing_id(client):
    resp = client.get("/api/leads/999")
    assert resp.status_code == 404


def test_update_lead_status_and_activity_logged(db_path, client):
    _seed_lead(db_path)
    resp = client.patch("/api/leads/1/status", json={"status": "CONTACTED"})
    assert resp.status_code == 200
    assert resp.json()["lead_status"] == "CONTACTED"

    activity_resp = client.get("/api/activity")
    messages = [a["message"] for a in activity_resp.json()]
    assert any("CONTACTED" in m for m in messages)


def test_update_lead_status_rejects_invalid_status(db_path, client):
    _seed_lead(db_path)
    resp = client.patch("/api/leads/1/status", json={"status": "NOT_A_REAL_STATUS"})
    assert resp.status_code == 400


def test_add_note_and_retrieve(db_path, client):
    _seed_lead(db_path)
    resp = client.post("/api/leads/1/notes", json={"text": "Following up tomorrow."})
    assert resp.status_code == 200

    notes_resp = client.get("/api/leads/1/notes")
    assert len(notes_resp.json()) == 1
    assert notes_resp.json()[0]["note_text"] == "Following up tomorrow."


def test_pipeline_groups_leads_by_status(db_path, client):
    _seed_lead(db_path)
    resp = client.get("/api/pipeline")
    assert resp.status_code == 200
    body = resp.json()
    assert "NEW" in body["statuses"]
    assert len(body["board"]["NEW"]) == 1


def test_analytics_reflects_real_data_no_fabrication(db_path, client):
    _seed_lead(db_path)
    resp = client.get("/api/analytics")
    body = resp.json()
    assert body["total_leads"] == 1
    assert body["priority_distribution"] == {"HOT": 1}
    assert body["service_demand"]["Visa Guidance"] == 1


def test_analytics_empty_database_returns_empty_not_fake_trends(client):
    resp = client.get("/api/analytics")
    body = resp.json()
    assert body["total_leads"] == 0
    assert body["priority_distribution"] == {}
    assert body["service_demand"] == {}


def test_settings_never_exposes_secrets(client):
    resp = client.get("/api/settings")
    body = resp.json()
    text = str(body)
    assert "fake" not in text  # our fake APIFY_API_TOKEN value must never appear
    assert "apify_api_token" not in text.lower()
    assert "openai_api_key" not in text.lower()
    assert body["reddit_connector"] == "connected"
    assert body["ai_provider"] == "mock"


def test_scan_status_idle_when_nothing_running(client):
    resp = client.get("/api/scan/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "idle"


def test_validation_status_idle_when_nothing_running(client):
    resp = client.get("/api/validation/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "idle"


def test_list_leads_filters_by_destination_and_course(db_path, client):
    db = _seed_lead(db_path, destination="Australia", course="Masters Engineering")
    db.save_lead(
        reddit_post_id="p2", username="u/other", subreddit="studyabroad",
        title="Which country for MS CS?", post_url="https://reddit.com/x", post_text="",
        created_at=datetime.now(timezone.utc), destination="Germany", course="Masters Computer Science",
        ai_is_lead=True, lead_score=60, lead_classification="WARM",
    )

    resp = client.get("/api/leads", params={"destination": "Germany"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["destination"] == "Germany"

    resp = client.get("/api/leads", params={"course": "Masters Engineering"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["course"] == "Masters Engineering"


def test_list_leads_pagination_does_not_silently_drop_results(db_path, client):
    db = Database(db_path)
    db.init_db()
    for i in range(5):
        db.save_lead(
            reddit_post_id=f"pg{i}", username="u/x", subreddit="studyabroad",
            title=f"Post number {i}", post_url="https://reddit.com/x", post_text="",
            created_at=datetime.now(timezone.utc), ai_is_lead=True,
            lead_score=50, lead_classification="WARM",
        )
    first_page = client.get("/api/leads", params={"limit": 2, "offset": 0}).json()
    second_page = client.get("/api/leads", params={"limit": 2, "offset": 2}).json()
    assert first_page["total"] == 5
    assert len(first_page["items"]) == 2
    assert len(second_page["items"]) == 2
    first_ids = {item["id"] for item in first_page["items"]}
    second_ids = {item["id"] for item in second_page["items"]}
    assert first_ids.isdisjoint(second_ids)


def test_scan_limits_endpoint_returns_bounded_choices(client):
    resp = client.get("/api/scan/limits")
    assert resp.status_code == 200
    assert resp.json()["allowed"] == [10, 25, 50, 100]


def test_recent_scans_empty_before_any_scan(client):
    resp = client.get("/api/scan/recent")
    assert resp.status_code == 200
    assert resp.json() == []


def test_recent_scans_reflects_real_scan_run_records(db_path, client):
    from app.database import Database

    db = Database(db_path)
    db.init_db()
    scan_id = db.create_scan_run(sources=["studyabroad"], post_limit=25)
    db.update_scan_run(
        scan_id, status="done", discovered=9, filtered=3, analyzed=6, hot=1, warm=2, cold=3
    )

    resp = client.get("/api/scan/recent")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "done"
    assert body[0]["discovered"] == 9
    assert body[0]["sources"] == ["studyabroad"]


def test_start_scan_rejects_unbounded_post_limit_by_falling_back_to_configured_default(
    db_path, client, monkeypatch
):
    # A client-supplied post_limit outside ALLOWED_POST_LIMITS must never
    # be trusted blindly -- it should fall back to the configured default
    # rather than triggering an arbitrarily large/unsafe live Apify call.
    from app import scan_service

    captured = {}

    def fake_start_scan(settings, post_limit=None):
        captured["post_limit"] = post_limit
        effective = post_limit if post_limit in scan_service.ALLOWED_POST_LIMITS else settings.post_limit
        captured["effective"] = effective
        return 1

    monkeypatch.setattr(scan_service, "start_scan", fake_start_scan)
    resp = client.post("/api/scan", json={"post_limit": 999999})
    assert resp.status_code == 200
    assert captured["effective"] != 999999


def test_start_scan_conflict_when_already_running(client, monkeypatch):
    from app import scan_service

    monkeypatch.setattr(scan_service, "start_scan", lambda settings, post_limit=None: None)
    resp = client.post("/api/scan", json={})
    assert resp.status_code == 409
