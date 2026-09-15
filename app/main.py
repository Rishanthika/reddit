"""
Main pipeline entry point.

Flow:

    Load environment
        -> Initialize database
        -> Initialize Reddit client
        -> Retrieve new posts
        -> Check duplicate
        -> Run keyword pre-filter
        -> If irrelevant -> skip (optionally recorded)
        -> If relevant -> AI classifier
        -> Calculate deterministic score
        -> HOT/WARM/COLD
        -> Save to SQLite
        -> Display lead in terminal

Run with:

    python -m app.main
"""

from __future__ import annotations

import logging
import sys

from app.ai_classifier import AIClassificationError, AnyAIClassifier, LeadAnalysis, create_ai_classifier
from app.config import ConfigError, Settings, load_settings
from app.database import Database, DatabaseError
from app.filters import FilterResult, filter_post
from app.lead_scoring import LeadScore, calculate_lead_score
from app.reddit_client import RedditClient, RedditClientError, RedditPost

logger = logging.getLogger(__name__)


def configure_logging(log_level: str) -> None:
    """Configure root logging. Never logs secrets — only operational events."""
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def supports_unicode() -> bool:
    """Best-effort check for whether stdout can render emoji/box characters."""
    encoding = (sys.stdout.encoding or "").lower()
    return "utf" in encoding


def display_lead(
    post: RedditPost,
    ai_result: LeadAnalysis,
    lead_score: LeadScore,
) -> None:
    """Print a HOT/WARM lead prominently; print COLD leads more quietly."""
    unicode_ok = supports_unicode()
    divider = "=" * 60

    if lead_score.classification == "HOT":
        banner = "🔥 NEW REDDIT LEAD (HOT)" if unicode_ok else "[HOT] NEW REDDIT LEAD"
    elif lead_score.classification == "WARM":
        banner = "🌤️  NEW REDDIT LEAD (WARM)" if unicode_ok else "[WARM] NEW REDDIT LEAD"
    else:
        # Keep COLD output minimal/quiet as required.
        print(f"[COLD] r/{post.subreddit} — {post.title[:70]} (score={lead_score.score})")
        return

    services = "\n".join(f"- {s}" for s in ai_result.service_needed) or "- (none specified)"

    print(divider)
    print(banner)
    print(divider)
    print()
    print(f"Score: {lead_score.score}/100")
    print(f"Classification: {lead_score.classification}")
    print()
    print(f"Student: {post.username}")
    print(f"Community: r/{post.subreddit}")
    print()
    print(f"Destination: {ai_result.destination or 'Unknown'}")
    print(f"Course: {ai_result.course or 'Unknown'}")
    print(f"Intent: {ai_result.intent.capitalize()}")
    print()
    print("Services:")
    print(services)
    print()
    print("Reason:")
    print(ai_result.reason)
    print()
    print("Post:")
    print(post.title)
    print()
    print("Reddit:")
    print(post.post_url)
    print()
    print("Status: NEW")
    print()
    print(divider)
    print()


def process_post(
    post: RedditPost,
    ai_classifier: AnyAIClassifier,
    database: Database,
) -> None:
    """Run one post through pre-filter -> AI -> scoring -> save -> display."""
    if database.is_duplicate(post.reddit_post_id):
        logger.debug("Skipping duplicate post %s", post.reddit_post_id)
        return

    filter_result: FilterResult = filter_post(post)

    if not filter_result.is_relevant:
        logger.debug(
            "Pre-filter rejected post %s: %s", post.reddit_post_id, filter_result.reason
        )
        return

    logger.info(
        "Post %s passed pre-filter (%s) — sending to AI classifier.",
        post.reddit_post_id,
        filter_result.reason,
    )

    try:
        ai_result = ai_classifier.classify(post)
    except AIClassificationError as exc:
        # Per spec: never invent a classification or score on AI failure.
        logger.error("AI classification failed for post %s: %s", post.reddit_post_id, exc)
        return

    lead_score = calculate_lead_score(ai_result, filter_result)

    try:
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
    except DatabaseError as exc:
        logger.error("Failed to save post %s: %s", post.reddit_post_id, exc)
        return

    display_lead(post, ai_result, lead_score)


def run(settings: Settings) -> None:
    """Execute one full pipeline pass over all configured subreddits."""
    database = Database(settings.database_path)
    database.init_db()

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

    logger.info(
        "Starting FutureGrad Reddit Lead Intelligence run — subreddits=%s, post_limit=%d",
        settings.subreddits,
        settings.post_limit,
    )

    processed = 0
    for post in reddit_client.fetch_new_posts(settings.post_limit):
        processed += 1
        process_post(post, ai_classifier, database)

    logger.info("Run complete. %d post(s) retrieved and evaluated.", processed)


def print_validation_result(
    post: RedditPost,
    ai_result: LeadAnalysis,
    lead_score: LeadScore,
) -> None:
    """
    Print the complete LeadAnalysis plus score for one post during
    classifier validation (CLASSIFIER_VALIDATION_MODE=true).

    Unlike `display_lead` (normal production output, which stays quiet for
    COLD leads by design), this always prints every field for every post
    that reached the classifier — validation exists specifically so false
    positives and false negatives are easy to spot, so a COLD result must
    be just as visible here as a HOT one.
    """
    service = ", ".join(ai_result.service_needed) if ai_result.service_needed else "Unknown"
    print(f"[{post.reddit_post_id}] r/{post.subreddit}")
    print(f"Title: {post.title}")
    print(f"Lead: {ai_result.is_lead}")
    print(f"Intent: {ai_result.intent}")
    print(f"Destination: {ai_result.destination or 'Unknown'}")
    print(f"Course: {ai_result.course or 'Unknown'}")
    print(f"Service: {service}")
    print(f"Reason: {ai_result.reason}")
    print(f"Confidence: {ai_result.confidence}")
    print(f"Score: {lead_score.score} ({lead_score.classification})")
    print("-" * 60)


def run_classifier_validation(settings: Settings) -> None:
    """
    Development/testing-only mode (CLASSIFIER_VALIDATION_MODE=true).

    Runs the same fetch -> subreddit validation -> relevance pre-filter ->
    AI classification -> deterministic scoring pipeline as `run()`, but:

      - the database's duplicate check does NOT gate whether a post is
        classified (so posts already collected in earlier runs can be
        re-evaluated against the current classifier);
      - this function performs ZERO database writes — `database.save_lead`
        is never called — so it can never create a duplicate row or
        mutate an existing one.

    Subreddit validation (RedditClient's own allowlist) and the relevance
    pre-filter both still apply exactly as in production, since this reuses
    the same `RedditClient.fetch_new_posts` and `filter_post` that `run()`
    uses — nothing about them is bypassed or reimplemented here.

    This is a read-only diagnostic tool, not a new production feature:
    normal behavior lives entirely in `run()`/`process_post()`, which this
    function does not call or modify.
    """
    database = Database(settings.database_path)
    database.init_db()

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

    logger.info(
        "CLASSIFIER VALIDATION MODE — subreddits=%s, validation_limit=%d, ai_provider=%s "
        "(read-only: no database writes will occur)",
        settings.subreddits,
        settings.classifier_validation_limit,
        settings.ai_provider,
    )

    retrieved = 0
    filtered_out = 0
    already_in_db = 0
    sent_to_classifier = 0
    ai_errors = 0
    classification_counts = {"HOT": 0, "WARM": 0, "COLD": 0}

    for post in reddit_client.fetch_new_posts(settings.classifier_validation_limit):
        retrieved += 1

        # Informational only in this mode — deliberately does NOT gate
        # whether the post reaches the classifier, unlike process_post().
        if database.is_duplicate(post.reddit_post_id):
            already_in_db += 1

        filter_result = filter_post(post)
        if not filter_result.is_relevant:
            filtered_out += 1
            continue

        sent_to_classifier += 1
        try:
            ai_result = ai_classifier.classify(post)
        except AIClassificationError as exc:
            ai_errors += 1
            logger.error("AI classification failed for post %s: %s", post.reddit_post_id, exc)
            continue

        lead_score = calculate_lead_score(ai_result, filter_result)
        classification_counts[lead_score.classification] += 1

        print_validation_result(post, ai_result, lead_score)
        # Deliberately no database.save_lead() call here — see docstring.

    print()
    print("=" * 60)
    print("CLASSIFIER VALIDATION SUMMARY (no database writes occurred)")
    print("=" * 60)
    print(f"Posts retrieved:              {retrieved}")
    print(f"Filtered out (pre-filter):    {filtered_out}")
    print(f"Already in database:          {already_in_db}  (informational only — not skipped)")
    print(f"Sent to classifier:           {sent_to_classifier}")
    print(f"AI classification errors:     {ai_errors}")
    print(f"HOT:                          {classification_counts['HOT']}")
    print(f"WARM:                         {classification_counts['WARM']}")
    print(f"COLD:                         {classification_counts['COLD']}")
    print("=" * 60)

    logger.info(
        "Validation complete. retrieved=%d filtered_out=%d already_in_db=%d "
        "sent_to_classifier=%d hot=%d warm=%d cold=%d errors=%d",
        retrieved,
        filtered_out,
        already_in_db,
        sent_to_classifier,
        classification_counts["HOT"],
        classification_counts["WARM"],
        classification_counts["COLD"],
        ai_errors,
    )


def main() -> int:
    """CLI entry point. Returns a process exit code."""
    try:
        settings = load_settings()
    except ConfigError as exc:
        # Configure basic logging so this is visible even before log_level is known.
        logging.basicConfig(level=logging.ERROR)
        logger.error("Configuration error: %s", exc)
        return 1

    configure_logging(settings.log_level)

    try:
        if settings.classifier_validation_mode:
            run_classifier_validation(settings)
        else:
            run(settings)
    except RedditClientError as exc:
        logger.error("Reddit client error: %s", exc)
        return 1
    except DatabaseError as exc:
        logger.error("Database error: %s", exc)
        return 1
    except Exception:  # last-resort safety net — never crash silently
        logger.exception("Unexpected error during pipeline run.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
