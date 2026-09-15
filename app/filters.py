"""
Keyword / rule-based pre-filter.

This is the first-stage filter, run entirely in Python before any post is
sent to the LLM. Its ONLY job is to cut LLM spend by eliminating content
with no configured study-abroad/admissions signal at all — it must NOT
attempt to decide whether a post is "really" a lead. That judgment belongs
entirely to the AI classifier (app/ai_classifier.py) and the deterministic
scorer (app/lead_scoring.py) downstream.

Redesigned per the FutureGrad lead-quality review (recall-oriented pass):
the previous version required 2+ distinct keyword groups (or one "strong"
standalone group) to match, which made the filter behave like a mini
lead-classifier — it silently discarded posts with a single, specific,
genuinely on-topic signal (e.g. an explicit admissions/application
question, or a bare degree mention) before the AI ever saw them. Now, any
ONE "qualifying" group match is enough (see QUALIFYING_GROUPS below). The
filter still rejects:
  - posts with zero configured keyword matches at all, and
  - posts whose only matches are generic noise words (e.g. just
    "university" on its own), and
  - posts whose only matched group is "countries" — a bare country
    mention (e.g. "Germany is beautiful") says nothing about study intent
    by itself and remains the classic false-positive trap.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List

from app.config import GENERIC_NOISE_WORDS, KEYWORD_GROUPS
from app.reddit_client import RedditPost

logger = logging.getLogger(__name__)

#: Groups that, by themselves, indicate a post is actually ABOUT the
#: study-abroad/admissions topic — not just incidental context. Any ONE of
#: these matching (with at least one non-noise keyword) is enough to let
#: the AI classifier evaluate the post. This is the core of the
#: recall-oriented redesign.
QUALIFYING_GROUPS = {"intent", "courses", "exams_documents", "admissions", "services"}

#: "countries" is deliberately excluded from QUALIFYING_GROUPS: a bare
#: country name says nothing about study intent on its own and is the
#: classic false-positive trap for a keyword filter (travel, news, sports,
#: general chatter). A country mention still counts as useful supporting
#: context once paired with any qualifying group.

#: Retained for logging/categorization only. Previously required for a
#: single group to count as relevant on its own; that gating role is gone
#: now that any QUALIFYING_GROUPS match is sufficient — this set now just
#: flags, in the reason string, which matched groups are the most
#: unambiguous (exams/documents, services) for anyone reading the logs.
STRONG_STANDALONE_GROUPS = {"exams_documents", "services"}


@dataclass(frozen=True)
class FilterResult:
    """Outcome of running the keyword pre-filter over a single post."""

    is_relevant: bool
    matched_keywords: List[str] = field(default_factory=list)
    matched_groups: List[str] = field(default_factory=list)
    pre_filter_score: int = 0
    reason: str = ""


def _find_matches(text: str, keywords: List[str]) -> List[str]:
    """
    Return the subset of `keywords` present in `text`.

    Matching is left-anchored on a word boundary but NOT right-anchored,
    so common inflections (e.g. "apply" -> "applying", "consultant" ->
    "consultants", "undergrad" -> "undergraduate"/"undergraduation") are
    still caught, while short/ambiguous keywords (e.g. "MS", "UK") still
    can't match in the middle of an unrelated word (e.g. "systems").
    """
    matches = []
    for kw in keywords:
        pattern = r"\b" + re.escape(kw.strip())
        if re.search(pattern, text, flags=re.IGNORECASE):
            matches.append(kw.strip())
    return matches


def filter_post(post: RedditPost) -> FilterResult:
    """
    Apply the lightweight, recall-oriented keyword pre-filter.

    A post is considered relevant (and passed to the AI classifier) when:

      1. At least one keyword matched at all, AND
      2. At least one of the matched keywords is not a bare generic/noise
         word (e.g. "university" on its own doesn't count), AND
      3. At least one matched group is a QUALIFYING_GROUPS group — i.e.
         the post is about intent, a course/degree, an exam/document, the
         admissions process, or an explicit service ask. A post whose
         ONLY matched group is "countries" does not qualify on its own.

    This deliberately does NOT try to decide whether the post is "really"
    a lead, how strong the intent is, or what HOT/WARM/COLD it might
    become — that's the AI classifier's and the deterministic scorer's
    job. This filter's only responsibility is to stop content with no
    configured signal at all from costing an AI call.
    """
    combined_text = f"{post.title} {post.post_text}".strip()

    matched_by_group: Dict[str, List[str]] = {}
    for group_name, keywords in KEYWORD_GROUPS.items():
        found = _find_matches(combined_text, keywords)
        if found:
            matched_by_group[group_name] = found

    if not matched_by_group:
        logger.debug("Pre-filter: no configured keywords matched at all.")
        return FilterResult(
            is_relevant=False,
            reason="No configured keywords matched.",
        )

    matched_groups = list(matched_by_group.keys())
    all_matched_keywords = sorted({kw for kws in matched_by_group.values() for kw in kws})

    # Guard against false positives from purely generic/noise words
    # matching with nothing else backing them up (e.g. just "university").
    non_noise_matches = {
        kw for kw in all_matched_keywords if kw.lower() not in GENERIC_NOISE_WORDS
    }

    qualifying_groups_matched = [g for g in matched_groups if g in QUALIFYING_GROUPS]

    is_relevant = bool(non_noise_matches) and bool(qualifying_groups_matched)

    pre_filter_score = len(matched_groups) * 10 + len(all_matched_keywords) * 2

    if is_relevant:
        strong_groups_matched = [g for g in matched_groups if g in STRONG_STANDALONE_GROUPS]
        reason = (
            f"Matched {len(matched_groups)} keyword group(s): {', '.join(matched_groups)} "
            f"(qualifying: {', '.join(qualifying_groups_matched)}"
            + (f"; strong: {', '.join(strong_groups_matched)}" if strong_groups_matched else "")
            + ")."
        )
        logger.debug(
            "Pre-filter PASSED post %s — matched groups=%s, qualifying=%s, keywords=%s",
            post.reddit_post_id, matched_groups, qualifying_groups_matched, all_matched_keywords,
        )
    elif not non_noise_matches:
        reason = (
            "Only generic/noise keyword(s) matched "
            f"({', '.join(all_matched_keywords)}); no substantive signal."
        )
        logger.debug(
            "Pre-filter REJECTED post %s — only noise keyword(s) matched: %s",
            post.reddit_post_id, all_matched_keywords,
        )
    else:
        reason = (
            "Only contextual/supporting group(s) matched "
            f"({', '.join(matched_groups)}) with no qualifying study-intent signal; "
            "needs at least one of intent/courses/exams_documents/admissions/services."
        )
        logger.debug(
            "Pre-filter REJECTED post %s — only supporting group(s) matched: %s",
            post.reddit_post_id, matched_groups,
        )

    return FilterResult(
        is_relevant=is_relevant,
        matched_keywords=all_matched_keywords,
        matched_groups=matched_groups,
        pre_filter_score=pre_filter_score,
        reason=reason,
    )
