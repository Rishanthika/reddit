"""
Reddit collection via Apify.

Phase 1 originally collected posts through the official Reddit API (PRAW).
That collection layer has been replaced with the Apify Actor
`automation-lab/reddit-scraper`, while keeping this module's public
interface and output schema identical to before, so filters.py,
ai_classifier.py, lead_scoring.py, database.py, and main.py did not need
to change:

    - The class is still called ``RedditClient``.
    - It still exposes ``fetch_new_posts(limit) -> Iterator[RedditPost]``.
    - ``RedditPost`` still has the same fields: reddit_post_id, username,
      subreddit, title, post_url, post_text, created_at.

Only ``RedditClient.__init__`` and its internals changed, to talk to Apify
instead of Reddit's OAuth API. ``main.py`` was updated only to pass the new
constructor arguments (Apify token/actor id instead of Reddit OAuth
credentials).

Design notes / constraints followed from the migration spec:

    - Only the Actor's default ("post") JSON output is used — never the
      `jsonl-finetune` or `rag-markdown` AI-oriented output formats, and
      never the Actor's own `filterKeywords` option. Phase 1's own
      keyword pre-filter (app/filters.py) and AI classifier
      (app/ai_classifier.py) remain the only filtering/AI stages.
    - Comments are never requested (`includeComments: False`).
    - Sort order is always "new".
    - Only records whose `subreddit` is in the configured SUBREDDITS
      allowlist are yielded; everything else the Actor returns is
      discarded.
    - A malformed individual record is logged and skipped, never allowed
      to crash the run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Set

from apify_client import ApifyClient
from apify_client.errors import ApifyClientError as _ApifyClientError

logger = logging.getLogger(__name__)


class RedditClientError(RuntimeError):
    """Raised when the Apify Actor run or dataset retrieval fails unrecoverably."""


@dataclass(frozen=True)
class RedditPost:
    """Normalized representation of a public Reddit submission (schema unchanged)."""

    reddit_post_id: str
    username: str
    subreddit: str
    title: str
    post_url: str
    post_text: str
    created_at: datetime


class RedditClient:
    """
    Collects new Reddit posts via the Apify Actor `automation-lab/reddit-scraper`.

    Public interface is unchanged from the PRAW-based version it replaces,
    so it is a drop-in replacement for the rest of the pipeline.
    """

    def __init__(self, apify_api_token: str, actor_id: str, subreddits: List[str]) -> None:
        self._subreddits = subreddits
        self._actor_id = actor_id
        try:
            self._client = ApifyClient(apify_api_token)
        except Exception as exc:  # defensive — the constructor itself rarely hits the network
            raise RedditClientError(f"Failed to initialize Apify client: {exc}") from exc

    def fetch_new_posts(self, limit: int) -> Iterator[RedditPost]:
        """
        Run the Apify Reddit Scraper Actor once for all configured subreddits
        and yield normalized RedditPost objects, newest first.

        Raises RedditClientError if the Actor run itself fails or the
        resulting dataset cannot be retrieved (caller — app/main.py — treats
        this the same way it treated a Reddit API failure before). Malformed
        individual records are logged and skipped rather than raised.
        """
        allowlist: Set[str] = {s.lower() for s in self._subreddits}

        run_input: Dict[str, Any] = {
            "urls": [f"https://www.reddit.com/r/{sub}/" for sub in self._subreddits],
            "maxPostsPerSource": limit,
            "sort": "new",
            "includeComments": False,
        }

        logger.info(
            "Starting Apify Reddit scraper... (actor=%s, subreddits=%s, limit=%d)",
            self._actor_id,
            self._subreddits,
            limit,
        )
        try:
            run = self._client.actor(self._actor_id).call(run_input=run_input)
        except _ApifyClientError as exc:
            raise RedditClientError(f"Apify Actor run failed: {exc}") from exc
        except Exception as exc:  # network/transport-level failure
            raise RedditClientError(f"Unexpected error running Apify Actor: {exc}") from exc
        logger.info("Apify Actor completed.")

        # apify-client >=3.x: `.actor(id).call(...)` returns a `Run` Pydantic
        # model (or None if it didn't complete), not a dict — so this must be
        # attribute access, not `.get(...)`.
        dataset_id = getattr(run, "default_dataset_id", None) if run is not None else None
        if not dataset_id:
            raise RedditClientError("Apify Actor run did not return a dataset id.")

        try:
            items = self._client.dataset(dataset_id).list_items().items
        except _ApifyClientError as exc:
            raise RedditClientError(f"Failed to retrieve Apify dataset: {exc}") from exc
        except Exception as exc:
            raise RedditClientError(f"Unexpected error retrieving Apify dataset: {exc}") from exc

        logger.info("Retrieved %d Reddit post(s).", len(items))

        yield from self._process_items(items, allowlist)

    def _process_items(
        self, items: List[Dict[str, Any]], allowlist: Set[str]
    ) -> Iterator[RedditPost]:
        """Filter, dedupe, and normalize raw Apify dataset records."""
        filtered_count = 0
        prepared_count = 0
        seen_ids: Set[str] = set()

        for item in items:
            if not isinstance(item, dict):
                logger.warning("Skipping non-object dataset item: %r", item)
                continue

            # Only ever use plain post records — never comments, and never
            # the Actor's jsonl-finetune/rag-markdown AI output types.
            record_type = item.get("type")
            if record_type not in (None, "post"):
                continue

            subreddit = str(item.get("subreddit") or "").strip()
            if subreddit.lower() not in allowlist:
                filtered_count += 1
                continue

            try:
                post = self._normalize(item)
            except Exception as exc:  # malformed record must not crash the run
                logger.warning(
                    "Skipping malformed Apify record (id=%s): %s",
                    item.get("id", "unknown"),
                    exc,
                )
                continue

            if post.reddit_post_id in seen_ids:
                # In-run duplicate safety net; database-level deduplication
                # (see app/database.py) remains the primary protection
                # across runs.
                continue
            seen_ids.add(post.reddit_post_id)

            prepared_count += 1
            yield post

        logger.info("Filtered %d post(s) outside configured subreddits.", filtered_count)
        logger.info("Prepared %d post(s) for lead analysis.", prepared_count)

    @staticmethod
    def _normalize(item: Dict[str, Any]) -> RedditPost:
        """
        Convert a single Apify `automation-lab/reddit-scraper` post record into
        the application's existing RedditPost schema.

        Field mapping:
            id          -> reddit_post_id
            author      -> username        ("[deleted]" if empty/missing)
            subreddit   -> subreddit
            title       -> title
            selfText    -> post_text       (may be empty; title remains usable)
            createdAt   -> created_at      (parsed ISO-8601, UTC)
            permalink / url -> post_url    (permalink preferred, url as fallback)
        """
        reddit_post_id = str(item.get("id") or "").strip()
        if not reddit_post_id:
            raise ValueError("Record is missing a usable 'id' field.")

        author = item.get("author")
        username = f"u/{author}" if author else "[deleted]"

        title = str(item.get("title") or "").strip()
        self_text = str(item.get("selfText") or "").strip()
        subreddit = str(item.get("subreddit") or "").strip()

        post_url = _resolve_post_url(item, subreddit, reddit_post_id)
        created_at = _parse_timestamp(item.get("createdAt"))

        return RedditPost(
            reddit_post_id=reddit_post_id,
            username=username,
            subreddit=subreddit,
            title=title,
            post_url=post_url,
            post_text=self_text,
            created_at=created_at,
        )


def _resolve_post_url(item: Dict[str, Any], subreddit: str, reddit_post_id: str) -> str:
    """Prefer the Actor's `permalink`, fall back to `url`, then a constructed URL."""
    permalink = str(item.get("permalink") or "").strip()
    if permalink:
        return permalink if permalink.startswith("http") else f"https://www.reddit.com{permalink}"

    url = str(item.get("url") or "").strip()
    if url:
        return url

    return f"https://www.reddit.com/r/{subreddit}/comments/{reddit_post_id}"


def _parse_timestamp(raw: Any) -> datetime:
    """Parse Apify's ISO-8601 `createdAt` into an aware UTC datetime."""
    if isinstance(raw, str) and raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Could not parse createdAt value %r; using current time.", raw)
    return datetime.now(timezone.utc)
