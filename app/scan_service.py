"""
Scan/validation orchestration for the FutureGrad web product layer.

This module is the ONLY thing new here — it does not modify, redesign, or
reimplement Reddit retrieval, filtering, classification, or scoring. It
calls the exact same building blocks `app/main.py` already uses
(`RedditClient`, `filter_post`, the AI classifier, `calculate_lead_score`,
`Database.save_lead`) in the same order, and adds:

  1. Discrete, real progress stages (discovering -> filtering ->
     analyzing -> scoring -> saving -> complete) so the web UI can show
     genuine backend progress instead of a fake animated bar. To report
     these as clearly separate stages, this module runs them as
     sequential PASSES over the retrieved posts (fetch all, then filter
     all, then classify all, then score all, then save all) rather than
     the CLI's per-post interleaved loop — this is an orchestration
     choice for UI reporting, not a change to what any of those calls do.
  2. Scan persistence (`Database.create_scan_run`/`update_scan_run`) so
     the Scan page can show a real "Recent Scans" history.
  3. A structured, in-memory result list for read-only validation runs,
     instead of printing to stdout (`app/main.py`'s
     `run_classifier_validation` is unchanged and still used by the CLI).

Both entry points below are safe to call repeatedly; a scan/validation
already in progress is not started twice.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Optional

from app.ai_classifier import AIClassificationError, create_ai_classifier
from app.config import Settings
from app.database import Database
from app.filters import filter_post
from app.lead_scoring import calculate_lead_score
from app.reddit_client import RedditClient, RedditClientError

_lock = threading.Lock()
_scan_state: dict = {
    "status": "idle",  # idle | starting | running | done | error
    "stage": "",  # discovering | filtering | analyzing | scoring | saving | complete
    "scan_id": None,
    "discovered": 0,
    "filtered": 0,
    "analyzed": 0,
    "hot": 0,
    "warm": 0,
    "cold": 0,
    "sources": [],
    "post_limit": None,
    "started_at": None,
    "finished_at": None,
    "error": None,
}

_validation_state: dict = {
    "status": "idle",
    "results": [],
    "summary": None,
    "finished_at": None,
    "error": None,
}

#: Sensible, bounded post-limit choices for the Scan page's selector.
#: Enforced server-side too — never trust the client's value blindly.
ALLOWED_POST_LIMITS = (10, 25, 50, 100)


def get_scan_state() -> dict:
    with _lock:
        return dict(_scan_state)


def get_validation_state() -> dict:
    with _lock:
        return {
            "status": _validation_state["status"],
            "results": list(_validation_state["results"]),
            "summary": _validation_state["summary"],
            "finished_at": _validation_state["finished_at"],
            "error": _validation_state["error"],
        }


def _set_scan(**kwargs) -> None:
    with _lock:
        _scan_state.update(kwargs)


def start_scan(settings: Settings, post_limit: Optional[int] = None) -> Optional[int]:
    """
    Start a production scan in a background thread. Returns the new scan's
    ID, or None if a scan is already running (never starts a second one
    concurrently).

    `post_limit`, if given, must be one of ALLOWED_POST_LIMITS — an
    unbounded or arbitrary client-supplied value is never accepted.
    Falls back to `settings.post_limit` (from `.env`) when not given.
    """
    effective_limit = post_limit if post_limit in ALLOWED_POST_LIMITS else settings.post_limit

    with _lock:
        if _scan_state["status"] in ("starting", "running"):
            return None
        _scan_state.update(
            status="starting",
            stage="",
            scan_id=None,
            discovered=0,
            filtered=0,
            analyzed=0,
            hot=0,
            warm=0,
            cold=0,
            sources=list(settings.subreddits),
            post_limit=effective_limit,
            started_at=datetime.now(timezone.utc).isoformat(),
            finished_at=None,
            error=None,
        )
    thread = threading.Thread(target=_run_scan, args=(settings, effective_limit), daemon=True)
    thread.start()
    return 1  # signals "started" to the caller; the real DB scan_id follows in get_scan_state()


def _run_scan(settings: Settings, post_limit: int) -> None:
    database = Database(settings.database_path)
    database.init_db()
    scan_run_id = database.create_scan_run(sources=list(settings.subreddits), post_limit=post_limit)
    _set_scan(status="running", stage="discovering", scan_id=scan_run_id)

    try:
        reddit_client = RedditClient(
            apify_api_token=settings.apify_api_token,
            actor_id=settings.apify_actor_id,
            subreddits=settings.subreddits,
        )
        ai_classifier = create_ai_classifier(
            provider=settings.ai_provider,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

        # Stage 1 — discovering: the real Apify-backed retrieval.
        posts = list(reddit_client.fetch_new_posts(post_limit))
        database.update_scan_run(scan_run_id, discovered=len(posts))
        _set_scan(discovered=len(posts), stage="filtering")

        # Stage 2 — filtering: the existing high-recall pre-filter, plus
        # the existing duplicate check (unchanged behavior from process_post).
        relevant = []
        filtered_out = 0
        for post in posts:
            if database.is_duplicate(post.reddit_post_id):
                filtered_out += 1
                continue
            filter_result = filter_post(post)
            if filter_result.is_relevant:
                relevant.append((post, filter_result))
            else:
                filtered_out += 1
        database.update_scan_run(scan_run_id, filtered=filtered_out)
        _set_scan(filtered=filtered_out, stage="analyzing")

        # Stage 3 — analyzing: the existing AI classifier, unchanged.
        classified = []
        for post, filter_result in relevant:
            try:
                ai_result = ai_classifier.classify(post)
            except AIClassificationError:
                continue
            classified.append((post, filter_result, ai_result))
        _set_scan(analyzed=len(classified), stage="scoring")

        # Stage 4 — scoring: the existing deterministic scorer, unchanged.
        scored = []
        hot = warm = cold = 0
        for post, filter_result, ai_result in classified:
            lead_score = calculate_lead_score(ai_result, filter_result)
            scored.append((post, filter_result, ai_result, lead_score))
            if lead_score.classification == "HOT":
                hot += 1
            elif lead_score.classification == "WARM":
                warm += 1
            else:
                cold += 1
        _set_scan(hot=hot, warm=warm, cold=cold, stage="saving")

        # Stage 5 — saving: the existing Database.save_lead, unchanged.
        for post, filter_result, ai_result, lead_score in scored:
            database.save_lead(
                reddit_post_id=post.reddit_post_id,
                username=post.username,
                subreddit=post.subreddit,
                title=post.title,
                post_url=post.post_url,
                post_text=post.post_text,
                created_at=post.created_at,
                destination=ai_result.destination,
                course=ai_result.course,
                intent=ai_result.intent,
                service_needed=ai_result.service_needed,
                ai_is_lead=ai_result.is_lead,
                ai_confidence=ai_result.confidence,
                ai_reason=ai_result.reason,
                pre_filter_score=filter_result.pre_filter_score,
                lead_score=lead_score.score,
                lead_classification=lead_score.classification,
            )

        database.update_scan_run(
            scan_run_id,
            status="done",
            analyzed=len(classified),
            hot=hot,
            warm=warm,
            cold=cold,
            finished_at=datetime.now(timezone.utc),
        )
        database.log_activity(
            "scan_completed",
            f"Reddit scan completed — {len(posts)} discovered, {len(classified)} analyzed, "
            f"{hot} HOT, {warm} WARM, {cold} COLD.",
        )
        _set_scan(status="done", stage="complete", finished_at=datetime.now(timezone.utc).isoformat())
    except RedditClientError as exc:
        database.update_scan_run(
            scan_run_id, status="error", error=str(exc), finished_at=datetime.now(timezone.utc)
        )
        database.log_activity("scan_failed", f"Reddit scan failed: {exc}")
        _set_scan(status="error", error=str(exc), finished_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:  # last-resort safety net, mirrors app/main.py's own
        database.update_scan_run(
            scan_run_id, status="error", error=str(exc), finished_at=datetime.now(timezone.utc)
        )
        database.log_activity("scan_failed", f"Reddit scan failed: {exc}")
        _set_scan(status="error", error=str(exc), finished_at=datetime.now(timezone.utc).isoformat())


def start_validation(settings: Settings) -> bool:
    """Start a READ-ONLY classifier validation run in a background thread.
    Never writes to the database — mirrors app/main.py's
    `run_classifier_validation`, but returns structured results instead
    of printing them."""
    with _lock:
        if _validation_state["status"] == "running":
            return False
        _validation_state.update(status="running", results=[], summary=None, finished_at=None, error=None)
    thread = threading.Thread(target=_run_validation, args=(settings,), daemon=True)
    thread.start()
    return True


def _run_validation(settings: Settings) -> None:
    database = Database(settings.database_path)
    database.init_db()
    try:
        reddit_client = RedditClient(
            apify_api_token=settings.apify_api_token,
            actor_id=settings.apify_actor_id,
            subreddits=settings.subreddits,
        )
        ai_classifier = create_ai_classifier(
            provider=settings.ai_provider,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

        retrieved = filtered_out = sent_to_classifier = ai_errors = 0
        counts = {"HOT": 0, "WARM": 0, "COLD": 0}
        results = []

        for post in reddit_client.fetch_new_posts(settings.classifier_validation_limit):
            retrieved += 1
            already_in_db = database.is_duplicate(post.reddit_post_id)

            filter_result = filter_post(post)
            if not filter_result.is_relevant:
                filtered_out += 1
                continue

            sent_to_classifier += 1
            try:
                ai_result = ai_classifier.classify(post)
            except AIClassificationError as exc:
                ai_errors += 1
                results.append(
                    {
                        "reddit_post_id": post.reddit_post_id,
                        "subreddit": post.subreddit,
                        "title": post.title,
                        "error": str(exc),
                    }
                )
                continue

            lead_score = calculate_lead_score(ai_result, filter_result)
            counts[lead_score.classification] += 1
            results.append(
                {
                    "reddit_post_id": post.reddit_post_id,
                    "subreddit": post.subreddit,
                    "title": post.title,
                    "already_in_db": already_in_db,
                    "is_lead": ai_result.is_lead,
                    "intent": ai_result.intent,
                    "destination": ai_result.destination,
                    "course": ai_result.course,
                    "service_needed": ai_result.service_needed,
                    "reason": ai_result.reason,
                    "confidence": ai_result.confidence,
                    "score": lead_score.score,
                    "classification": lead_score.classification,
                }
            )

        summary = {
            "retrieved": retrieved,
            "filtered_out": filtered_out,
            "sent_to_classifier": sent_to_classifier,
            "ai_errors": ai_errors,
            "hot": counts["HOT"],
            "warm": counts["WARM"],
            "cold": counts["COLD"],
        }
        database.log_activity(
            "validation_completed",
            f"Validation completed — {retrieved} retrieved, {sent_to_classifier} classified, "
            f"{counts['HOT']} HOT, {counts['WARM']} WARM, {counts['COLD']} COLD.",
        )
        with _lock:
            _validation_state.update(
                status="done",
                results=results,
                summary=summary,
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
    except RedditClientError as exc:
        with _lock:
            _validation_state.update(
                status="error", error=str(exc), finished_at=datetime.now(timezone.utc).isoformat()
            )
    except Exception as exc:
        with _lock:
            _validation_state.update(
                status="error", error=str(exc), finished_at=datetime.now(timezone.utc).isoformat()
            )
