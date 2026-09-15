"""
Centralized configuration for the FutureGrad Reddit Lead Intelligence System.

All environment-driven settings are loaded and validated here so the rest
of the application can simply import ``settings`` (or call ``load_settings()``)
instead of reading ``os.environ`` in multiple places.

Business-logic constants that are not secrets (keyword groups, scoring
weights, thresholds) also live here so they can be tuned without touching
the pipeline logic in ``app/main.py``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    """Strongly-typed application settings loaded from environment variables."""

    apify_api_token: str
    apify_actor_id: str

    ai_provider: str

    openai_api_key: str
    openai_model: str

    subreddits: List[str]
    post_limit: int

    database_path: str

    log_level: str

    classifier_validation_mode: bool
    classifier_validation_limit: int


def _require(name: str) -> str:
    """Fetch a required environment variable or raise a clear ConfigError."""
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise ConfigError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill in a value for {name}."
        )
    return value.strip()


def load_settings(env_file: str = ".env") -> Settings:
    """
    Load and validate application settings.

    Parameters
    ----------
    env_file:
        Path to a dotenv file to load before reading os.environ. Defaults
        to ``.env`` in the current working directory. Safe to call even if
        the file does not exist (python-dotenv simply no-ops).

    Raises
    ------
    ConfigError
        If any required environment variable is missing or invalid.
    """
    load_dotenv(dotenv_path=env_file, override=False)

    apify_api_token = _require("APIFY_API_TOKEN")
    apify_actor_id = os.getenv("APIFY_ACTOR_ID", "automation-lab/reddit-scraper").strip()

    ai_provider = os.getenv("AI_PROVIDER", "openai").strip().lower()
    valid_providers = {"openai", "mock"}
    if ai_provider not in valid_providers:
        raise ConfigError(
            f"AI_PROVIDER must be one of {sorted(valid_providers)}, got {ai_provider!r}."
        )

    # OPENAI_API_KEY is only required when actually talking to OpenAI. In
    # AI_PROVIDER=mock mode the key is never read or used, so it must not
    # block startup — this lets developers test the full pipeline without
    # an OpenAI account or credits.
    if ai_provider == "openai":
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not openai_api_key:
            raise ConfigError(
                "OPENAI_API_KEY is required when AI_PROVIDER=openai. "
                "Set it in your .env file, or set AI_PROVIDER=mock for local "
                "development without an OpenAI account."
            )
    else:
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    subreddits_raw = os.getenv("SUBREDDITS", "studyabroad,gradadmissions")
    subreddits = [s.strip() for s in subreddits_raw.split(",") if s.strip()]
    if not subreddits:
        raise ConfigError(
            "SUBREDDITS must contain at least one subreddit name, e.g. "
            "SUBREDDITS=studyabroad,gradadmissions"
        )

    try:
        post_limit = int(os.getenv("POST_LIMIT", "25"))
    except ValueError as exc:
        raise ConfigError("POST_LIMIT must be an integer.") from exc
    if post_limit <= 0:
        raise ConfigError("POST_LIMIT must be a positive integer.")

    database_path = os.getenv("DATABASE_PATH", "data/leads.db").strip()

    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if log_level not in valid_levels:
        raise ConfigError(
            f"LOG_LEVEL must be one of {sorted(valid_levels)}, got {log_level!r}."
        )

    # Development/testing-only: lets the current AI_PROVIDER be validated
    # against posts already sitting in the database from earlier runs,
    # without the normal duplicate gate or any database writes. Defaults
    # to disabled so production behavior (run()) is completely unaffected
    # unless explicitly opted into.
    classifier_validation_mode = os.getenv("CLASSIFIER_VALIDATION_MODE", "false").strip().lower() in (
        "1", "true", "yes", "on",
    )

    try:
        classifier_validation_limit = int(os.getenv("CLASSIFIER_VALIDATION_LIMIT", "30"))
    except ValueError as exc:
        raise ConfigError("CLASSIFIER_VALIDATION_LIMIT must be an integer.") from exc
    if classifier_validation_limit <= 0:
        raise ConfigError("CLASSIFIER_VALIDATION_LIMIT must be a positive integer.")

    return Settings(
        apify_api_token=apify_api_token,
        apify_actor_id=apify_actor_id,
        ai_provider=ai_provider,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        subreddits=subreddits,
        post_limit=post_limit,
        database_path=database_path,
        log_level=log_level,
        classifier_validation_mode=classifier_validation_mode,
        classifier_validation_limit=classifier_validation_limit,
    )


# ---------------------------------------------------------------------------
# Business-logic constants (not secrets — safe to keep in source control).
# ---------------------------------------------------------------------------

#: Keyword groups used by the Phase-1 pre-filter (app/filters.py).
#: Grouped so the filter can reason about *which kinds* of signal fired,
#: not just a flat keyword hit.
KEYWORD_GROUPS: dict[str, List[str]] = {
    "intent": [
        "study abroad",
        "study overseas",
        "masters abroad",
        "master's abroad",
        "international student",
        "foreign university",
        "abroad education",
    ],
    "courses": [
        "ms ",
        "msc",
        "mba",
        "master",  # stem: matches master/masters/master's (also covers "masters", "master's" below)
        "masters",
        "master's",
        "phd",
        "doctorate",
        "doctoral",
        "undergrad",  # stem: matches undergrad/undergraduate/undergraduation
        "undergraduate",
        "bachelor",  # stem: matches bachelor/bachelors/bachelor's
        "bachelors",
    ],
    "exams_documents": [
        "ielts",
        "toefl",
        "gre",
        "gmat",
        "sop",
        "lor",
        "cv",
        "resume",
    ],
    "countries": [
        "germany",
        "uk",
        "united kingdom",
        "usa",
        "united states",
        "canad",  # stem: matches canada/canadian
        "australia",
        "ireland",
        "netherlands",
        "france",
        "italy",
        "spain",
        "japan",
        "sweden",
        "finland",
        "denmark",
        "new zealand",
        "singapore",
        "uae",
        "united arab emirates",
    ],
    "admissions": [
        "univers",  # stem: matches university/universities
        "admission",
        "application",
        "apply",
        "deadline",
        "offer letter",
        "intake",
        "course selection",
        "university selection",
    ],
    "services": [
        "consultant",
        "counselling",
        "counseling",
        "guidance",
        "application help",
        "visa",
        "sop help",
        "admission help",
    ],
}

#: Generic words that, on their own, must never qualify a post as relevant.
#: Used to avoid false positives like "best laptop for college".
GENERIC_NOISE_WORDS = {"college", "school", "student", "study", "univers"}

#: The old "MIN_MATCHING_GROUPS = 2" cross-signal requirement was removed
#: as part of the lead-quality review: it made the pre-filter behave like
#: a mini lead-classifier instead of a lightweight recall gate. See
#: app/filters.py's QUALIFYING_GROUPS for the replacement logic — any ONE
#: qualifying group (intent/courses/exams_documents/admissions/services)
#: is now enough to let the AI classifier evaluate the post.

#: Deterministic scoring weights (see app/lead_scoring.py).
#:
#: Revised per the FutureGrad lead-quality review: the four signals that
#: your own HOT philosophy calls out as independently decisive (explicit
#: counselling/consultant ask, actively applying/admission ask, immediate
#: visa/SOP assistance ask, and the AI's own "high confidence" intent
#: rating) were previously weighted so low that no realistic single-topic
#: Reddit post could cross the HOT threshold even with a perfect AI
#: classification. Destination/course/university-selection (your WARM-tier
#: examples) and the unrelated-post penalty are unchanged.
SCORING_WEIGHTS = {
    "explicit_counselling_request": 45,
    "asking_how_where_to_apply": 30,
    "specific_destination": 15,
    "specific_course": 10,
    "university_selection_question": 15,
    "visa_application_sop_guidance": 20,
    "strong_study_abroad_intent": 15,
    "general_study_abroad_discussion": 5,
    "clearly_unrelated": -50,
}

#: Score thresholds for HOT / WARM / COLD classification.
SCORE_MIN = 0
SCORE_MAX = 100
HOT_THRESHOLD = 80
WARM_THRESHOLD = 50
