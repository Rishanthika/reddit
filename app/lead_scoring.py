"""
Deterministic lead scoring.

`app/ai_classifier.py` determines WHETHER a post is a genuine prospective
lead and WHAT it means (intent, destination, course, service_needed). This
module is the single source of truth for converting that structured
`LeadAnalysis` into a numeric priority score and HOT/WARM/COLD
classification. It does not re-derive or second-guess the classifier's
semantic judgment — it trusts `is_lead` and `intent` completely and scores
strictly from the structured fields already on `LeadAnalysis`.

Architectural boundary (see the lead-scoring-calibration task that produced
this version): earlier revisions of this module re-inspected the keyword
pre-filter's raw matched-keyword list as a proxy for "was a service really
requested". That blurred the classifier/scorer boundary — the scorer was
quietly re-doing keyword-based semantic detection. This version uses
*only* `LeadAnalysis` fields; `filter_result` is still accepted (kept for
call-site compatibility with `app/main.py`, which isn't part of this
task's scope) but its contents no longer affect the score at all.

Scoring model:

    is_lead == False                          -> score forced to 0 (COLD)
    Intent base:
        high     +80   (already HOT on its own — matches the philosophy
                         that a concrete, immediate personal need/problem
                         is HOT-worthy by itself)
        medium   +50   (already WARM on its own — a genuine personal
                         decision/comparison/evaluation lead is WARM-worthy
                         even with service_needed=Unknown)
        low      +10   (stays COLD on its own; a weak/unspecific lead
                         should not be promoted merely because is_lead=True)
        none      +0
    Specificity (modest, additive, never required for WARM):
        destination is not Unknown             +10
        course is not Unknown                  +10
    Explicit ask:
        service_needed is not empty            +15

`confidence` is deliberately NOT used as a scoring input — the calibration
task explicitly cautions against letting confidence alone push a weak lead
up, and the simplest way to honor that is not to wire it in at all.

Final score is clamped to [0, 100]. Thresholds (unchanged):

    80-100 = HOT
    50-79  = WARM
    0-49   = COLD
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from app.ai_classifier import LeadAnalysis
from app.config import HOT_THRESHOLD, SCORE_MAX, SCORE_MIN, WARM_THRESHOLD
from app.filters import FilterResult

LeadClassification = str  # "HOT" | "WARM" | "COLD"

#: Base score from the classifier's own intent judgment. Set so that
#: "high" alone already clears the HOT floor and "medium" alone already
#: clears the WARM floor — the classifier's semantic intent judgment is
#: trusted outright, not treated as merely one signal among many.
_INTENT_BASE_WEIGHTS = {
    "high": 80,
    "medium": 50,
    "low": 10,
    "none": 0,
}

#: Modest, additive specificity bonuses. Deliberately small relative to
#: the intent bases above so that stacking every bonus on a "low" intent
#: lead still cannot reach "medium"'s base alone (10 + 10 + 10 + 15 = 45,
#: still under medium's 50) — see the lead-scoring-calibration task's
#: explicit requirement that a genuine medium-intent lead must not be
#: outranked by a low-intent lead merely because the latter has a
#: destination.
_SPECIFIC_DESTINATION_BONUS = 10
_SPECIFIC_COURSE_BONUS = 10
_EXPLICIT_SERVICE_BONUS = 15


@dataclass(frozen=True)
class LeadScore:
    """Final deterministic scoring result for a single lead."""

    score: int
    classification: LeadClassification
    applied_rules: List[str] = field(default_factory=list)


def _classify(score: int) -> LeadClassification:
    if score >= HOT_THRESHOLD:
        return "HOT"
    if score >= WARM_THRESHOLD:
        return "WARM"
    return "COLD"


def calculate_lead_score(ai_result: LeadAnalysis, filter_result: FilterResult) -> LeadScore:
    """
    Calculate the final deterministic lead score from the classifier's
    structured output alone.

    Parameters
    ----------
    ai_result:
        Validated structured output from the AI classifier — the only
        input that actually drives the score.
    filter_result:
        Accepted for call-site compatibility with `app/main.py` only.
        Its contents are not inspected — the scorer trusts `ai_result`
        completely rather than re-checking the raw pre-filter keywords.

    Returns
    -------
    LeadScore
        The clamped score, its HOT/WARM/COLD classification, and a list
        of the named rules that were applied (for transparency/debugging).
    """
    del filter_result  # intentionally unused — see module docstring

    if not ai_result.is_lead:
        return LeadScore(score=0, classification="COLD", applied_rules=["not_a_lead"])

    applied_rules: List[str] = []
    intent = ai_result.intent if ai_result.intent in _INTENT_BASE_WEIGHTS else "none"
    score = _INTENT_BASE_WEIGHTS[intent]
    applied_rules.append(f"intent_{intent}")

    if ai_result.destination:
        score += _SPECIFIC_DESTINATION_BONUS
        applied_rules.append("specific_destination")

    if ai_result.course:
        score += _SPECIFIC_COURSE_BONUS
        applied_rules.append("specific_course")

    if ai_result.service_needed:
        score += _EXPLICIT_SERVICE_BONUS
        applied_rules.append("explicit_service_requested")

    final_score = max(SCORE_MIN, min(SCORE_MAX, score))
    return LeadScore(
        score=final_score,
        classification=_classify(final_score),
        applied_rules=applied_rules,
    )
