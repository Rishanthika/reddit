"""
Tests for app/main.py's pipeline orchestration — both normal production
mode (`run`) and the classifier-validation mode (`run_classifier_validation`).

No real Apify or OpenAI calls are made anywhere in this file — the Apify
client is replaced with the same in-memory fake used in
tests/test_reddit_client.py, and the AI classifier is a small spy so we can
assert exactly which posts it was (or wasn't) called with.
"""

import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.ai_classifier import LeadAnalysis
from app.config import Settings
from app.database import Database
from app.main import run, run_classifier_validation

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeListItemsResult:
    def __init__(self, items):
        self.items = items


class _FakeDatasetClient:
    def __init__(self, items):
        self._items = items

    def list_items(self):
        return _FakeListItemsResult(self._items)


class _FakeActorClient:
    def call(self, run_input=None):
        return SimpleNamespace(default_dataset_id="dataset-1")


class _FakeApifyClient:
    """Stand-in for apify_client.ApifyClient — never touches the network."""

    def __init__(self, items):
        self._items = items

    def __call__(self, token):  # used as `ApifyClient(token)` in reddit_client.py
        return self

    def actor(self, actor_id):
        return _FakeActorClient()

    def dataset(self, dataset_id):
        return _FakeDatasetClient(self._items)


class _SpyClassifier:
    """Records every post it's asked to classify; always returns a fixed lead."""

    def __init__(self):
        self.calls = []

    def classify(self, post):
        self.calls.append(post.reddit_post_id)
        return LeadAnalysis(
            is_lead=True,
            intent="medium",
            destination="Germany",
            course="Masters",
            service_needed=["Application Guidance"],
            reason="spy classifier",
            confidence=0.7,
        )


def _apify_post(post_id, title, subreddit="studyabroad", self_text=""):
    return {
        "type": "post",
        "id": post_id,
        "title": title,
        "author": "someone",
        "subreddit": subreddit,
        "createdAt": "2026-09-10T00:00:00.000Z",
        "permalink": f"/r/{subreddit}/comments/{post_id}/x/",
        "selfText": self_text,
    }


@pytest.fixture()
def db_path():
    path = tempfile.mktemp(suffix=".db")
    yield path
    if os.path.exists(path):
        os.remove(path)


def _make_settings(db_path, validation_mode=False, validation_limit=30, post_limit=10):
    return Settings(
        apify_api_token="fake",
        apify_actor_id="automation-lab/reddit-scraper",
        ai_provider="mock",
        openai_api_key="",
        openai_model="gpt-4o-mini",
        subreddits=["studyabroad", "gradadmissions"],
        post_limit=post_limit,
        database_path=db_path,
        log_level="INFO",
        classifier_validation_mode=validation_mode,
        classifier_validation_limit=validation_limit,
    )


_RELEVANT_TITLE = "Need a consultant for my Master's application in Germany"
_IRRELEVANT_TITLE = "Which laptop should I buy for college?"


def _seed_existing_lead(db_path, reddit_post_id, **overrides):
    """Insert a pre-existing lead row directly, simulating an earlier run."""
    db = Database(db_path)
    db.init_db()
    defaults = dict(
        reddit_post_id=reddit_post_id,
        username="u/original",
        subreddit="studyabroad",
        title="Original title from an earlier run",
        post_url=f"https://reddit.com/r/studyabroad/comments/{reddit_post_id}",
        post_text="",
        created_at=datetime.now(timezone.utc),
        destination="Original Destination",
        course="Original Course",
        intent="low",
        service_needed=["Original Service"],
        ai_is_lead=True,
        ai_confidence=0.42,
        ai_reason="original reason from earlier run",
        pre_filter_score=5,
        lead_score=13,
        lead_classification="COLD",
    )
    defaults.update(overrides)
    db.save_lead(**defaults)


def _get_lead_row(db_path, reddit_post_id):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM leads WHERE reddit_post_id = ?", (reddit_post_id,)
    ).fetchone()
    conn.close()
    return row


def _count_leads(db_path):
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    conn.close()
    return count


# ---------------------------------------------------------------------------
# Normal mode (run)
# ---------------------------------------------------------------------------


def test_normal_mode_skips_existing_duplicate(db_path):
    _seed_existing_lead(db_path, "p1")
    fake_apify = _FakeApifyClient([_apify_post("p1", _RELEVANT_TITLE)])
    spy = _SpyClassifier()
    settings = _make_settings(db_path)

    with patch("app.reddit_client.ApifyClient", fake_apify), \
         patch("app.main.create_ai_classifier", return_value=spy):
        run(settings)

    assert spy.calls == []  # never reached the classifier — duplicate gate held
    assert _count_leads(db_path) == 1  # still just the original seeded row


def test_normal_mode_processes_a_genuinely_new_post(db_path):
    fake_apify = _FakeApifyClient([_apify_post("p_new", _RELEVANT_TITLE)])
    spy = _SpyClassifier()
    settings = _make_settings(db_path)

    with patch("app.reddit_client.ApifyClient", fake_apify), \
         patch("app.main.create_ai_classifier", return_value=spy):
        run(settings)

    assert spy.calls == ["p_new"]
    assert _count_leads(db_path) == 1


# ---------------------------------------------------------------------------
# Classifier validation mode (run_classifier_validation)
# ---------------------------------------------------------------------------


def test_validation_mode_allows_existing_post_to_reach_classifier(db_path):
    _seed_existing_lead(db_path, "p1")
    fake_apify = _FakeApifyClient([_apify_post("p1", _RELEVANT_TITLE)])
    spy = _SpyClassifier()
    settings = _make_settings(db_path, validation_mode=True)

    with patch("app.reddit_client.ApifyClient", fake_apify), \
         patch("app.main.create_ai_classifier", return_value=spy):
        run_classifier_validation(settings)

    assert spy.calls == ["p1"]  # duplicate did NOT block classification


def test_validation_mode_does_not_insert_duplicate_record(db_path):
    _seed_existing_lead(db_path, "p1")
    fake_apify = _FakeApifyClient([_apify_post("p1", _RELEVANT_TITLE)])
    spy = _SpyClassifier()
    settings = _make_settings(db_path, validation_mode=True)

    with patch("app.reddit_client.ApifyClient", fake_apify), \
         patch("app.main.create_ai_classifier", return_value=spy):
        run_classifier_validation(settings)

    assert _count_leads(db_path) == 1  # no new row was inserted


def test_validation_mode_does_not_modify_existing_lead(db_path):
    _seed_existing_lead(
        db_path, "p1",
        lead_score=13, lead_classification="COLD", ai_reason="original reason from earlier run",
    )
    fake_apify = _FakeApifyClient([_apify_post("p1", _RELEVANT_TITLE)])
    spy = _SpyClassifier()  # would report a very different result (medium/Germany/Masters)
    settings = _make_settings(db_path, validation_mode=True)

    with patch("app.reddit_client.ApifyClient", fake_apify), \
         patch("app.main.create_ai_classifier", return_value=spy):
        run_classifier_validation(settings)

    row = _get_lead_row(db_path, "p1")
    assert row["lead_score"] == 13
    assert row["lead_classification"] == "COLD"
    assert row["ai_reason"] == "original reason from earlier run"


def test_validation_mode_respects_relevance_filter(db_path):
    fake_apify = _FakeApifyClient([_apify_post("p_irrelevant", _IRRELEVANT_TITLE)])
    spy = _SpyClassifier()
    settings = _make_settings(db_path, validation_mode=True)

    with patch("app.reddit_client.ApifyClient", fake_apify), \
         patch("app.main.create_ai_classifier", return_value=spy):
        run_classifier_validation(settings)

    assert spy.calls == []  # pre-filter still gates classification in validation mode


def test_validation_mode_respects_subreddit_validation(db_path):
    # This post's subreddit is not in the configured SUBREDDITS allowlist,
    # even though its title would otherwise pass the relevance filter.
    fake_apify = _FakeApifyClient(
        [_apify_post("p_wrong_sub", _RELEVANT_TITLE, subreddit="totally_unrelated_subreddit")]
    )
    spy = _SpyClassifier()
    settings = _make_settings(db_path, validation_mode=True)

    with patch("app.reddit_client.ApifyClient", fake_apify), \
         patch("app.main.create_ai_classifier", return_value=spy):
        run_classifier_validation(settings)

    assert spy.calls == []  # RedditClient's own allowlist already dropped it


def test_validation_mode_never_writes_to_database_even_for_new_posts(db_path):
    # A genuinely new (never-seen) post must ALSO not be written to the DB
    # in validation mode — this mode is read-only, full stop.
    fake_apify = _FakeApifyClient([_apify_post("p_brand_new", _RELEVANT_TITLE)])
    spy = _SpyClassifier()
    settings = _make_settings(db_path, validation_mode=True)

    with patch("app.reddit_client.ApifyClient", fake_apify), \
         patch("app.main.create_ai_classifier", return_value=spy):
        run_classifier_validation(settings)

    assert spy.calls == ["p_brand_new"]
    assert _count_leads(db_path) == 0


def test_validation_output_includes_complete_lead_analysis(db_path, capsys):
    # Part 1 fix: validation output must show the full LeadAnalysis (not
    # just id/subreddit/title/classification/score), so false positives
    # and false negatives are easy to spot per §21 of the architecture spec.
    fake_apify = _FakeApifyClient([_apify_post("p_full", _RELEVANT_TITLE)])
    spy = _SpyClassifier()  # returns a fixed LeadAnalysis — see class above
    settings = _make_settings(db_path, validation_mode=True)

    with patch("app.reddit_client.ApifyClient", fake_apify), \
         patch("app.main.create_ai_classifier", return_value=spy):
        run_classifier_validation(settings)

    out = capsys.readouterr().out

    assert "p_full" in out
    assert "r/studyabroad" in out
    assert _RELEVANT_TITLE in out
    assert "Lead: True" in out
    assert "Intent: medium" in out
    assert "Destination: Germany" in out
    assert "Course: Masters" in out
    assert "Application Guidance" in out
    assert "Reason: spy classifier" in out
    assert "Confidence: 0.7" in out
    assert "Score:" in out
    assert "WARM" in out or "HOT" in out or "COLD" in out


def test_validation_output_shows_full_analysis_even_for_cold_non_leads(db_path, capsys):
    # Unlike normal production output (which stays quiet for COLD leads),
    # validation output must show every field even when is_lead is False —
    # that's exactly the case validation mode exists to make visible.
    class _NonLeadSpy:
        def classify(self, post):
            return LeadAnalysis(
                is_lead=False,
                intent="none",
                destination=None,
                course=None,
                service_needed=[],
                reason="no signals found",
                confidence=0.5,
            )

    fake_apify = _FakeApifyClient([_apify_post("p_cold", _RELEVANT_TITLE)])
    settings = _make_settings(db_path, validation_mode=True)

    with patch("app.reddit_client.ApifyClient", fake_apify), \
         patch("app.main.create_ai_classifier", return_value=_NonLeadSpy()):
        run_classifier_validation(settings)

    out = capsys.readouterr().out

    assert "p_cold" in out
    assert "Lead: False" in out
    assert "Destination: Unknown" in out
    assert "Course: Unknown" in out
    assert "Service: Unknown" in out
    assert "Reason: no signals found" in out
