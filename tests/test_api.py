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

    # Used as a context manager so FastAPI's lifespan (startup/shutdown)
    # actually runs — that's what calls Database.init_db() once at
    # startup now, instead of api.py doing it on every request.
    with TestClient(app) as test_client:
        yield test_client


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


# ---------------------------------------------------------------------------
# CORS configuration
# ---------------------------------------------------------------------------


def test_cors_allows_local_dev_origin(client):
    resp = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_allows_the_real_deployed_vercel_origin(client):
    resp = client.get("/api/health", headers={"Origin": "https://reddit-futuregrad.vercel.app"})
    assert resp.headers.get("access-control-allow-origin") == "https://reddit-futuregrad.vercel.app"


def test_cors_allows_the_current_production_vercel_origin(client):
    resp = client.get("/api/health", headers={"Origin": "https://reddit-sigma-ruddy.vercel.app"})
    assert resp.headers.get("access-control-allow-origin") == "https://reddit-sigma-ruddy.vercel.app"


def test_cors_does_not_allow_arbitrary_origins(client):
    resp = client.get("/api/health", headers={"Origin": "https://some-random-site.example.com"})
    assert resp.headers.get("access-control-allow-origin") is None


def test_cors_never_uses_wildcard():
    from app.api import _cors_origins

    assert "*" not in _cors_origins()


def test_cors_respects_frontend_url_env_var_additively(monkeypatch):
    from app.api import _cors_origins, _DEFAULT_CORS_ORIGINS

    monkeypatch.setenv("FRONTEND_URL", "https://custom-domain.example.com")
    origins = _cors_origins()

    assert "https://custom-domain.example.com" in origins
    # additive, not a replacement -- the defaults (including localhost) remain
    for default in _DEFAULT_CORS_ORIGINS:
        assert default in origins


def test_cors_frontend_url_trailing_slash_is_normalized(monkeypatch):
    from app.api import _cors_origins

    monkeypatch.setenv("FRONTEND_URL", "https://custom-domain.example.com/")
    origins = _cors_origins()

    assert "https://custom-domain.example.com" in origins
    assert "https://custom-domain.example.com/" not in origins


def test_cors_blank_frontend_url_does_not_add_empty_origin(monkeypatch):
    from app.api import _cors_origins

    monkeypatch.setenv("FRONTEND_URL", "")
    origins = _cors_origins()

    assert "" not in origins


# ---------------------------------------------------------------------------
# Database initialization idempotency (init_db regression: "table leads
# already exists"). See app/database.py's init_db() docstring.
# ---------------------------------------------------------------------------


def test_init_db_can_be_called_twice_on_the_same_database_without_error(db_path):
    db = Database(db_path)
    db.init_db()  # first call: creates the schema
    db.init_db()  # second call: schema already exists -- must not raise


def test_init_db_from_a_second_database_instance_on_same_file_is_safe(db_path):
    # Simulates api.py's old per-request pattern of constructing a brand
    # new Database (and therefore a brand new engine) against a file that
    # already has the schema from an earlier instance/process.
    Database(db_path).init_db()
    Database(db_path).init_db()  # different instance, same underlying file


def test_init_db_preserves_existing_data_across_repeated_calls(db_path):
    db = Database(db_path)
    db.init_db()
    db.save_lead(
        reddit_post_id="preserve-me", username="u/test", subreddit="studyabroad",
        title="Existing lead that must survive re-initialization",
        post_url="https://reddit.com/x", post_text="",
        created_at=datetime.now(timezone.utc), ai_is_lead=True,
        lead_score=90, lead_classification="HOT",
    )

    # Re-initializing (as would happen on every restart/reload) must never
    # drop or reset the table.
    Database(db_path).init_db()
    Database(db_path).init_db()

    leads = Database(db_path).list_leads()
    assert leads["total"] == 1
    assert leads["items"][0]["reddit_post_id"] == "preserve-me"


def test_init_db_creates_all_four_tables_not_just_leads(db_path):
    import sqlite3

    Database(db_path).init_db()
    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()

    assert {"leads", "lead_notes", "activity_log", "scan_runs"}.issubset(tables)


def test_init_db_tolerates_a_concurrent_toctou_style_race(db_path, monkeypatch):
    """
    Directly reproduces the reported failure mode: `create_all()` sees the
    table doesn't exist yet (checkfirst passes), but by the time it issues
    CREATE TABLE, another caller has already created it -- SQLite then
    raises `OperationalError: table leads already exists`. init_db() must
    treat that specific outcome as success, not propagate it as a
    DatabaseError.
    """
    from sqlalchemy.exc import OperationalError

    db = Database(db_path)

    def racy_create_all(engine, checkfirst=True):
        # Simulate: something else created the table between the
        # checkfirst query and this call's own CREATE TABLE statement.
        raise OperationalError(
            "CREATE TABLE leads (...)", {}, Exception("table leads already exists")
        )

    monkeypatch.setattr(
        "app.database.Base.metadata.create_all", racy_create_all
    )

    db.init_db()  # must not raise DatabaseError despite the simulated race


def test_init_db_still_raises_on_a_genuine_unrelated_database_error(db_path, monkeypatch):
    from app.database import DatabaseError
    from sqlalchemy.exc import OperationalError

    db = Database(db_path)

    def broken_create_all(engine, checkfirst=True):
        raise OperationalError("CREATE TABLE leads (...)", {}, Exception("disk I/O error"))

    monkeypatch.setattr("app.database.Base.metadata.create_all", broken_create_all)

    with pytest.raises(DatabaseError):
        db.init_db()


def test_backend_startup_initializes_schema_once_not_per_request(db_path, client):
    # The `client` fixture enters TestClient as a context manager, which
    # runs the FastAPI lifespan startup -- confirm that alone is already
    # enough for the schema to exist, with no per-request init_db() call
    # needed (app/api.py's _get_database() no longer calls it).
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()
    assert "leads" in tables

    # And a normal request still works against that already-initialized schema.
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
