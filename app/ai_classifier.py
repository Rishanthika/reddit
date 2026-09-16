"""
AI lead classification.

Sends pre-filtered posts to the OpenAI API and parses the response into a
strict, validated structure. This module NEVER decides the final numeric
lead score or HOT/WARM/COLD classification — it only extracts semantic
signals. Deterministic scoring lives in app/lead_scoring.py.

If the AI call fails, times out, or returns invalid JSON, this module
raises AIClassificationError. Callers must treat that as "classification
unavailable" and must NOT invent a lead classification or score.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import List, Literal, Optional, Union

from openai import APIError, APITimeoutError, OpenAI
from pydantic import BaseModel, Field, ValidationError

from app.reddit_client import RedditPost

logger = logging.getLogger(__name__)

IntentLevel = Literal["high", "medium", "low", "none"]

#: Keeps the OpenAI request bounded/cheap regardless of how long a Reddit
#: post's body is. A lead-qualification judgment doesn't need the entire
#: text of a long post; this is a cost-control measure, not a quality one.
_MAX_BODY_CHARS = 2000

#: This prompt encodes the same lead-quality principles the deterministic
#: mock classifier was calibrated against across multiple validation
#: rounds (see app/ai_classifier.py's MockAIClassifier section below for
#: the equivalent deterministic rules) — it is NOT the original generic
#: "is this about study abroad?" prompt. Keeping the two classifiers
#: aligned on the same judgment principles is intentional: the mock
#: exists to let the rest of the pipeline be tested against the same
#: quality bar the real model is expected to meet.
SYSTEM_PROMPT = """\
You are a lead-qualification analyst for FutureGrad, a study-abroad \
admissions consultancy. You will be shown the title and body of a single \
public Reddit post. Your job is to decide whether the POSTER THEMSELVES \
is showing genuine personal prospective study-abroad/admissions intent \
that a FutureGrad counsellor could realistically help with — not whether \
the post merely mentions study-abroad-related topics.

============================================================
CORE PRINCIPLE: PERSONAL INTENT, NOT TOPIC PRESENCE
============================================================
Never classify a post as a lead just because it contains words like \
"study abroad", "university", "visa", "masters", "PhD", "scholarship", \
"USA", "UK", "Australia", "Germany", etc. Those are topic signals, not \
proof of personal intent. A post is only a lead when it represents the \
POSTER'S OWN decision, problem, plan, or explicit request for help.

Treat these as NOT leads (is_lead = false), even when they use plenty of \
study-abroad vocabulary:
- General/hypothetical norm questions with no personal framing, e.g. \
"Does GPA matter for admission?", "Are publications required for PhD \
applications?", "What are the requirements to study in Germany?" — \
compare with the PERSONAL versions of the same questions ("Does MY GPA \
matter?", "...for MY PhD application?", "...for ME to study in \
Germany?"), which ARE leads.
- Retrospective/experience-sharing posts: "How was your experience with \
X?", "International students who dropped out: how are things going for \
you now?"
- Community discussion inviting others to share, without the poster \
stating their own plan: "Anyone else planning to apply for a Master's \
abroad in 2027?" (contrast with a poster explicitly asking about THEIR \
OWN plan, comparison, or decision).
- Third-party questions not about the poster's own application: "What's \
appropriate to ask a PhD student helping with a professor's applicant \
review?"
- Commentary/opinion/rant posts: "Why nobody tells you the real UK job \
market reality before you take out a masters loan."
- Generic informational or resource-sharing posts, announcements, or \
warnings: "This might be a helpful resource for those applying to grad \
school", "Announcement: Beware of [scam]."
- Bare noun-phrase or vague titles with no real request: "Sciences Po", \
"Best business majors", "Please tell me your opinion" (with no personal \
plan stated in the body either).
- Generic CV/application discussion where personal study-abroad intent \
isn't clearly established, or unrelated financial questions.

Treat these as genuine LEADS (is_lead = true):
- Explicit personal decision/comparison questions: "Which universities \
should I target for MS CS in the USA/Ireland?", "Which European country \
should I consider for a Master's?", "Should I do a Master's abroad or \
work for a year first?"
- Personal profile/feasibility evaluation: "How realistic is an MSF for \
me with a 3.6 GPA?", "What are my chances of getting into a PhD \
program?", "How good is my profile for the 2027 MS intake?"
- Concrete personal problems: an actual visa appointment issue, a \
specific application problem, "I am facing issues with my visa \
appointment."
- Explicit requests for counselling, application/CV/SOP review, visa \
help, or scholarship help.

A genuine lead can still be true even when service_needed ends up empty \
— e.g. "which country should I choose?" is a real personal decision lead \
with no specific service requested yet.

============================================================
DESTINATION
============================================================
Only extract a destination the poster is clearly personally targeting. \
If the post explicitly compares MULTIPLE destinations for the poster's \
own decision (e.g. "USA vs Ireland", "Australia, USA, or Canada?"), do \
NOT arbitrarily pick one — represent it as a single joined string, e.g. \
"USA / Ireland" or "Australia / USA / Canada". If no destination is \
clearly supported, use null. Never infer a destination from unrelated \
context elsewhere in the post.

============================================================
COURSE / DEGREE
============================================================
Distinguish the poster's CURRENT or background degree from their TARGET \
degree — e.g. "I have a B.Tech in Mechanical Engineering, want to pursue \
an MS in Data Science" targets "Masters Data Science", not the \
background Mechanical Engineering. Prefer a specific stated field over a \
generic one (e.g. "Masters Business Analytics" rather than just \
"Masters Business" if Business Analytics is what's actually named). If \
no degree/field is clearly supported, use null — never invent one.

============================================================
SERVICE NEEDED
============================================================
Only include a service when the post actually requests or clearly needs \
it (e.g. "Can someone review my SOP?" -> SOP help; "How do I get a visa \
appointment?" -> visa guidance; explicit request for a consultant -> \
counselling). Do not infer a service merely from adjacent keywords. A \
real personal decision lead with no explicit service ask should have an \
empty service_needed list, not a fabricated one.

============================================================
INTENT
============================================================
- "high": a concrete, immediate personal problem or explicit request \
for help right now (a real visa/application problem, an explicit \
counselling request, an urgent deadline/appointment issue).
- "medium": genuine personal planning, comparison, or evaluation without \
immediate urgency (country/university/degree choice, profile or \
feasibility evaluation, "should I do X or Y" decisions).
- "low": weak/unclear personal relevance with no clear decision or \
request.
- "none": not a lead at all.
Do not assign "high" merely because the post contains many study-abroad \
keywords — base it on genuine urgency/concreteness.

============================================================
REASON AND CONFIDENCE
============================================================
"reason" must describe only what is actually present in the post — never \
invent evidence that isn't there. "confidence" should reflect genuine \
certainty in this specific judgment, not be inflated just because many \
topic words are present.

============================================================
OUTPUT FORMAT
============================================================
Respond with ONLY a single JSON object (no markdown, no commentary) \
matching exactly this shape:

{
  "is_lead": <boolean>,
  "intent": "high" | "medium" | "low" | "none",
  "destination": <string or null>,
  "course": <string or null>,
  "service_needed": [<string>, ...],
  "reason": <short string>,
  "confidence": <number between 0 and 1>
}
"""


class AIClassificationError(RuntimeError):
    """Raised when the AI classifier cannot produce a valid result."""


class LeadAnalysis(BaseModel):
    """Strict schema for the structured output returned by the LLM."""

    is_lead: bool
    intent: IntentLevel
    destination: Optional[str] = None
    course: Optional[str] = None
    service_needed: List[str] = Field(default_factory=list)
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class AIClassifier:
    """Wraps the OpenAI API to classify a pre-filtered Reddit post."""

    def __init__(self, api_key: str, model: str) -> None:
        # max_retries=0 disables the SDK's own automatic retry-on-429/5xx
        # behavior. This is intentional cost control: one Reddit post must
        # correspond to at most one OpenAI request, and any failure
        # (including a 429) should surface immediately as
        # AIClassificationError rather than silently multiplying calls.
        self._client = OpenAI(api_key=api_key, max_retries=0)
        self._model = model

    def classify(self, post: RedditPost) -> LeadAnalysis:
        """
        Classify a single post. Raises AIClassificationError on any
        failure (network, API, or schema validation) — callers must not
        fabricate a result on failure. Never logs the API key or any
        authorization header; logs only the provider, model, post id,
        elapsed time, and (on failure) the exception type as an error
        category.
        """
        body = post.post_text or ""
        if len(body) > _MAX_BODY_CHARS:
            body = body[:_MAX_BODY_CHARS] + " …(truncated)"

        user_prompt = (
            f"Subreddit: r/{post.subreddit}\n"
            f"Title: {post.title}\n"
            f"Body: {body if body else '(no body text)'}"
        )

        started = time.perf_counter()
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
        except APITimeoutError as exc:
            self._log_failure(post, started, "APITimeoutError")
            raise AIClassificationError("OpenAI request timed out.") from exc
        except APIError as exc:
            self._log_failure(post, started, type(exc).__name__)
            raise AIClassificationError(f"OpenAI API error: {type(exc).__name__}") from exc
        except Exception as exc:  # unexpected transport-level failure
            self._log_failure(post, started, type(exc).__name__)
            raise AIClassificationError(
                f"Unexpected OpenAI client error: {type(exc).__name__}"
            ) from exc

        raw_content = response.choices[0].message.content if response.choices else None
        if not raw_content:
            self._log_failure(post, started, "EmptyResponse")
            raise AIClassificationError("OpenAI response contained no content.")

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            self._log_failure(post, started, "InvalidJSON")
            raise AIClassificationError(f"OpenAI response was not valid JSON: {exc}") from exc

        try:
            result = LeadAnalysis.model_validate(parsed)
        except ValidationError as exc:
            self._log_failure(post, started, "SchemaValidationError")
            raise AIClassificationError(
                f"OpenAI response did not match the expected schema: {exc}"
            ) from exc

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "AI classification succeeded (provider=openai, model=%s, post=%s, "
            "elapsed_ms=%d, is_lead=%s, intent=%s)",
            self._model, post.reddit_post_id, elapsed_ms, result.is_lead, result.intent,
        )
        return result

    def _log_failure(self, post: RedditPost, started: float, error_category: str) -> None:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.error(
            "AI classification failed (provider=openai, model=%s, post=%s, "
            "elapsed_ms=%d, error_category=%s)",
            self._model, post.reddit_post_id, elapsed_ms, error_category,
        )


# ---------------------------------------------------------------------------
# Mock classifier — for development/testing only, no OpenAI calls.
# ---------------------------------------------------------------------------
#
# Returns the SAME `LeadAnalysis` schema as `AIClassifier`, using purely
# deterministic keyword/rule logic instead of a real model call. This exists
# so the rest of the pipeline (pre-filter -> classifier -> deterministic
# scoring -> database) can be exercised end-to-end without spending OpenAI
# credits. It is NOT a stand-in for real classification quality.
#
# Design note (post lead-quality review): every extracted field is derived
# from ONE shared pass over the post's actual text, and the `reason` string
# is built from exactly the same matched terms used to set destination/
# course/service_needed/intent — so the reason can never mention a signal
# that wasn't actually used. Destination/degree/field are searched in the
# TITLE first, falling back to the body only if nothing is found there,
# since Reddit post bodies on study-abroad subreddits often contain
# boilerplate submission templates (e.g. a "choose your country" checklist)
# that can mention countries or services the poster never actually meant.

_COUNTRY_KEYWORDS: List[tuple] = [
    ("united kingdom", "UK"),
    ("uk", "UK"),
    ("united states", "USA"),
    ("usa", "USA"),
    ("australia", "Australia"),
    ("canadian", "Canada"),
    ("canada", "Canada"),
    ("germany", "Germany"),
    ("netherlands", "Netherlands"),
    ("ireland", "Ireland"),
    ("france", "France"),
    ("spain", "Spain"),
    ("italy", "Italy"),
    ("sweden", "Sweden"),
    ("finland", "Finland"),
    ("denmark", "Denmark"),
    ("new zealand", "New Zealand"),
    ("japan", "Japan"),
    ("singapore", "Singapore"),
    ("united arab emirates", "UAE"),
    ("uae", "UAE"),
    ("poland", "Poland"),
    ("malaysia", "Malaysia"),
]

#: Degree/level stems. Left-anchored substring matching (see `_iter_matches`)
#: so common inflections are caught: "undergrad" also matches "undergraduate"
#: and "undergraduation"; "bachelor" also matches "bachelors"/"bachelor's";
#: "master" also matches "masters"/"master's". "ms" is the common bare
#: abbreviation ("MS in Germany") that predates "MSc" spelled out.
#: NOTE: "b.tech"/"btech" are deliberately NOT included here. They almost
#: always describe the poster's completed/current (background) degree, not
#: the degree they're asking about — treating it as a target-degree signal
#: would misattribute background info as intent (see field-priority logic
#: below for the same principle applied to field-of-study).
_DEGREE_KEYWORDS: List[tuple] = [
    ("msc", "MSc"),
    ("msf", "MSF"),  # Master of Science in Finance — a real, common abbreviation
    ("mtech", "Masters"),  # Master of Technology — common in Indian academic contexts
    ("ms", "Masters"),
    ("mba", "MBA"),
    ("phd", "PhD"),
    ("doctorate", "PhD"),
    ("doctoral", "PhD"),
    ("undergrad", "Undergraduate"),
    ("bachelor", "Undergraduate"),
    ("master", "Masters"),
]

#: Field-of-study stems, IN PRIORITY ORDER (not the order they happen to
#: appear in the text — see `_first_priority_match`). Specific fields
#: (Computer Science / CS / CSE / Data Science) are checked before the
#: generic "engineer" stem, so a post that mentions BOTH a background like
#: "B.Tech Engineering" and a target like "MS CS" correctly resolves to
#: Computer Science rather than the more generic Engineering label that
#: happens to also be present.
_FIELD_KEYWORDS: List[tuple] = [
    ("computer science", "Computer Science"),
    ("cse", "Computer Science"),
    ("cs", "Computer Science"),
    ("data science", "Data Science"),
    ("artificial intelligence", "Artificial Intelligence"),
    ("cybersecurity", "Cybersecurity"),
    ("business analytics", "Business Analytics"),
    ("business", "Business"),
    ("econom", "Economics"),
    ("financ", "Finance"),
    ("manage", "Management"),
    ("medic", "Medicine"),
    ("law", "Law"),
    ("engineer", "Engineering"),
]

#: (service label, trigger keywords) — a post only earns a service label if
#: one of ITS OWN keywords is actually present; categories never bleed into
#: each other (e.g. asking whether a program is "good" never triggers
#: Scholarship Guidance, since "scholarship"/"funding"/"financial aid" are
#: the only things that can trigger that specific label).
_SERVICE_CATEGORIES: List[tuple] = [
    ("Scholarship Guidance", ["scholarship", "funding", "financial aid"]),
    ("Application Guidance", ["admission", "application", "applying", "apply", "acceptance", "university eligibility", "requirement"]),
    ("Counselling", ["consultant", "consultancy", "counsellor", "counseling", "counselling"]),
    ("Visa Guidance", ["visa"]),
    ("SOP Guidance", ["sop", "statement of purpose"]),
    ("Test Preparation Guidance", ["ielts", "toefl", "english proficiency"]),
]
#: NOTE: "guidance" and "recommendation" were deliberately REMOVED as bare
#: Counselling triggers (they used to be here). They're too generic/weak on
#: their own — a vague plea like "hello everybody, I need guidance please"
#: was being read as an explicit consultant request, which then also
#: auto-granted HIGH intent. Counselling now requires an unambiguous word
#: for the specific service (consultant/consultancy/counsellor/
#: counseling/counselling).

#: Phrases that indicate genuine study-abroad planning/comparison even when
#: no specific service is being asked for — e.g. "are they good for
#: undergraduation in business?" is a real lead (evaluating a program) even
#: though it doesn't ask for a consultant, visa, or scholarship.
_GENERIC_INTEREST_KEYWORDS = [
    "good for",
    "good option",
    "which university",
    "which universities",
    "which course",
    "which is better",
    "compare",
    "comparing",
    "worth it",
    "should i choose",
    "which country",
    "recommend a university",
    "makes more sense",
    "what makes sense",
]

#: "which university"/"which country" above only match when nothing sits
#: between the two words. A real Reddit title often inserts an adjective
#: ("which EUROPEAN country", "which particular course") or asks "which
#: one" — this regex allows up to two words in between so that phrasing
#: isn't missed. Contributes to the same generic-interest/comparison
#: signal as the literal phrases above, not a separate substance category.
_WHICH_DECISION_REGEX = re.compile(
    r"\bwhich\s+(?:\w+\s+){0,2}(?:countr\w*|universit\w*|course|one)\b",
    re.IGNORECASE,
)

#: Per the FutureGrad intent philosophy: these mean the poster is ready for
#: immediate assistance right now.
_HIGH_INTENT_PHRASES = [
    "applying now",
    "application deadline",
    "admission problem",
    "urgent visa",
    "visa issue",
]

#: Combined with an actual service signal (visa/scholarship/SOP/etc.),
#: these situational/problem/help-request words push intent to HIGH —
#: matching the philosophy's "urgent/current application issue... actively
#: making a decision with immediate consequences" (e.g. "Stuck waiting for
#: a study visa slot with zero availability", "I am facing issues with the
#: visa appointment", "Can someone review my CV before I apply?"). These
#: words alone, with no real service need, do NOT grant HIGH intent —
#: only the combination does, so a routine mention of "deadline" in an
#: unrelated context can't push intent up by itself.
_URGENCY_MARKERS = [
    "stuck",
    "zero availability",
    "no slots",
    "urgent",
    "asap",
    "running out of time",
    "last minute",
    "facing issues",
    "facing a problem",
    "facing an application problem",
    "facing a visa problem",
    "application problem",
    "visa problem",
    "visa appointment problem",
    "can't get",
    "cannot get",
    "unable to",
    "how to avoid",
    "can i get admission",
    "appointment unavailable",
    "deadline",
    "help me",
    "i need help",
    "review my application",
    "review my cv",
    "review my sop",
    "application help",
    "visa help",
    "scholarship help",
]

#: Per the philosophy: researching/comparing/planning, not yet immediate.
_MEDIUM_INTENT_PHRASES = [
    "compare",
    "comparing",
    "which university",
    "which universities",
    "which course",
    "which is better",
    "planning",
    "recommend",
    "recommendation",
    "should i choose",
    "should i",
    "good for",
    "good option",
    "worth it",
    "how good is my profile",
    "my profile",
    "profile evaluation",
    "realistic",  # left-anchored stem: also matches "realistically"
    "or work",  # "abroad or work ... first" — the study-vs-work-first decision framing
    "chanc",  # left-anchored stem: "my chances", "what are my chances", "a chance"
    "for me",
    "i want to",
    "considering",
    "cv help",
]

#: Signals that a post is chatter/noise rather than a personal study-abroad
#: lead, even if it happens to mention an otherwise-relevant word.
_NON_LEAD_SIGNAL_KEYWORDS: List[str] = [
    "meme",
    "shitpost",
    "joke",
    "jokes",
    "breaking news",
    "news:",
]

#: Phrases indicating the TITLE already poses a complete, self-contained
#: comparison/decision question (e.g. "which is better X or Y", "X vs Y"),
#: even when the specific entities named (university names, cities) aren't
#: recognized by any of our keyword lists. When this is true, we do NOT
#: fall back to the post body for destination/degree/field — doing so is
#: exactly what caused a post asking "Monash Malaysia or University of
#: Auckland" to have an unrelated "Singapore"/"PhD"/"Data Science" mention
#: from later in the body misattributed to the question in the title.
_COMPARISON_PHRASE_MARKERS = [
    "versus",
    "which is better",
    "compare",
    "comparing",
    "which one",
]
_COMPARISON_WORD_MARKERS = ["vs"]  # matched with full word boundaries

#: A post that's explicitly SHARING something for other people's benefit
#: ("this might be a helpful resource for those applying..."), or that's an
#: announcement/warning rather than a personal ask ("Announcement: Beware
#: of..."), is not itself a personal admissions ask — even though it may
#: use words like "applying" or "scholarship" that would otherwise look
#: like real substance. Requires one of these AND the absence of a
#: personal marker (below) to avoid misclassifying a genuine personal
#: question that happens to mention a resource ("I found this resource but
#: still need advice on my case").
_RESOURCE_SHARING_MARKERS = [
    "helpful resource",
    "this might help",
    "this might be helpful",
    "sharing this",
    "in case this helps",
    "here's a resource",
    "here is a resource",
    "compilation of",
    "psa:",
    "fyi:",
    "resource for those",
    "guide for those",
    "announcement:",
    "beware of",
    "warning:",
    "scam alert",
    "be careful of",
    "anyone else",
    "anyone here",
    "for those who",
    "people who",
    "how was your experience",
    "what was your experience",
    "job market reality",
    "nobody tells you",
    "applicant review",
]

#: Presence of any of these means the post IS about the poster's own
#: situation, overriding the resource-sharing/announcement check above,
#: and also counts toward "request framing" for service-only substance
#: (see `has_request_framing` in `classify`).
_PERSONAL_MARKERS = [
    "i am",
    "i'm",
    "i need",
    "i want",
    "my application",
    "help me",
    "should i",
    "can i",
    "am i",
    "for me",
    "my situation",
    "i have",
    "i've",
    "advice for me",
    "my profile",
    "my chances",
    "my case",
    "my gpa",
    "my visa",
    "my scholarship",
    "i am applying",
    "i want to study",
    "how do i",
    "how should i",
]

#: A vague, generic plea with NO other specific detail (no destination,
#: course, comparison, or real service need) is ambiguous content — per
#: the is_lead decision hierarchy, ambiguous content should NOT default to
#: being a lead ("Hello everybody please help 🙏" is not itself a lead;
#: what matters is whether the post states an actual need).
_VAGUE_PLEA_MARKERS = [
    "please help",
    "help me please",
    "somebody help",
    "anybody help",
    "need help",
    "hello everybody",
    "hello everyone",
]

#: A bare service-category keyword (visa/scholarship/SOP/etc.) is only
#: treated as real substance when there's also some sign the poster is
#: asking about THEIR OWN situation — otherwise a purely informational or
#: news-style mention ("Visa rules are changing across Europe this year")
#: would incorrectly become a lead. Any personal marker, a question mark,
#: or one of these request-framing phrases satisfies that requirement.
_REQUEST_FRAMING_MARKERS = [
    "need",
    "want",
    "looking for",
    "how do i",
    "how should i",
    "can i",
    "should i",
    "help me",
    "advice on",
    "any tips",
    "any advice",
]

#: Broader, single-word personal-framing pronouns, used ONLY to unlock
#: service-only substance (see `has_request_framing`). Deliberately kept
#: separate from `_PERSONAL_MARKERS` (used for the resource-sharing/
#: announcement override): a resource-sharing post can innocently contain
#: "I" ("I hope this helps someone") without actually being a personal
#: ask, so that override needs the more specific phrase list instead.
_BARE_PRONOUN_MARKERS = ["i", "my", "me"]

#: A post asking about a general NORM or RULE ("Are publications a MUST
#: when applying...", "What are the visa REQUIREMENTS for international
#: students?") is not itself a personal ask, even when it names a real
#: degree/service/topic and ends in a question mark — a bare "?" is not
#: reliable evidence of personal intent, since general and personal
#: questions are phrased identically that way. Requires the absence of a
#: personal marker or bare pronoun to override (the personal version of
#: the SAME question, e.g. "Are MY publications enough for MY PhD
#: application?", is not caught by this list and remains a lead).
_GENERAL_QUESTION_MARKERS = [
    "a must",
    "requirements",
    "best",
]

#: A "does X matter" framing ("Does GPA matter for admission?", "Does
#: Bachelor Grade matter a lot in application?"), or an "is/are X
#: required/necessary" framing ("Are publications required for PhD
#: applications?"), is the same general-norm question shape as
#: `_GENERAL_QUESTION_MARKERS` above, just needing a pattern rather than a
#: literal phrase since a degree/topic word sits in between.
_GENERAL_NORM_QUESTION_REGEX = re.compile(
    r"\bdoes\s+(?:\w+\s+){0,3}matter\b"
    r"|\b(?:is|are)\s+(?:\w+\s+){0,3}(?:required|necessary)\b",
    re.IGNORECASE,
)


def _keyword_pattern(keyword: str) -> str:
    """
    Build the regex pattern for one keyword. Very short (<=3 char)
    alphabetic keywords (e.g. "ms", "uk", "cs", "cse", "usa") get a FULL
    word boundary on both sides so they can't match as a prefix of an
    unrelated longer word; longer/more specific keywords keep the
    left-anchor-only convention (catches inflections like "undergrad" ->
    "undergraduate"/"undergraduation").
    """
    escaped = re.escape(keyword)
    if len(keyword) <= 3 and keyword.isalpha():
        return r"\b" + escaped + r"\b"
    return r"\b" + escaped


def _iter_matches(text: str, keyword_specs: List[tuple]) -> List[tuple]:
    """
    Return (position, label, matched_keyword) for every keyword_specs entry
    found in `text`, in the order they appear in the text (leftmost first).
    """
    hits = []
    for keyword, label in keyword_specs:
        match = re.search(_keyword_pattern(keyword), text, flags=re.IGNORECASE)
        if match:
            hits.append((match.start(), label, keyword))
    hits.sort(key=lambda hit: hit[0])
    return hits


def _dedupe_labels_in_order(hits: List[tuple]) -> List[str]:
    """From a position-sorted (position, label, keyword) list, return the
    distinct labels in order of first appearance."""
    seen: List[str] = []
    for _, label, _ in hits:
        if label not in seen:
            seen.append(label)
    return seen


def _first_priority_match(text: str, keyword_specs: List[tuple]) -> Optional[tuple]:
    """
    Return (label, matched_keyword) for the FIRST entry in `keyword_specs`
    (list order = priority order) whose keyword is found ANYWHERE in
    `text`, or None.

    Unlike `_iter_matches`, this ignores WHERE in the text a keyword
    occurs — list order encodes priority instead. Used for field-of-study
    extraction so a specific field (e.g. "computer science") wins over a
    generic one ("engineer") even if the generic term happens to appear
    earlier in the raw text (e.g. "B.Tech Engineering ... MS in Computer
    Science" should resolve to Computer Science, not Engineering).
    """
    for keyword, label in keyword_specs:
        if re.search(_keyword_pattern(keyword), text, flags=re.IGNORECASE):
            return label, keyword
    return None


def _title_has_comparison_markers(text: str) -> bool:
    """
    True if `text` poses an explicit multi-option comparison/decision
    question (e.g. "which is better X or Y", "X vs Y") even if the named
    entities aren't in any of our keyword lists.
    """
    for phrase in _COMPARISON_PHRASE_MARKERS:
        if re.search(_keyword_pattern(phrase), text, flags=re.IGNORECASE):
            return True
    for word in _COMPARISON_WORD_MARKERS:
        if re.search(r"\b" + re.escape(word) + r"\b", text, flags=re.IGNORECASE):
            return True
    return False


def _title_has_any_topical_signal(title: str) -> bool:
    """
    True if the TITLE ALONE contains any country/degree/field/service/
    comparison/generic-interest signal.

    Used to decide whether the body can be trusted to supplement the
    title at all. A title with genuinely no topical anchor ("Please tell
    me your opinion") gives no reason to believe unrelated content
    appearing later in the body is actually about the SAME thing the
    title is asking about — that's exactly how a vague title ended up
    with five hallucinated destination countries pulled from unrelated
    body text. A title with at least one real signal (even just a
    service keyword, with no country) is a legitimate anchor for body
    supplementation, e.g. "Need advice on my upcoming application" +
    body "I'm targeting Germany".

    Deliberately checks topical keywords only — NOT personal markers/
    pronouns — since a phrase like "please tell ME your opinion" contains
    "me" without being any kind of real anchor.
    """
    if _iter_matches(title, _COUNTRY_KEYWORDS):
        return True
    if _iter_matches(title, _DEGREE_KEYWORDS):
        return True
    if _first_priority_match(title, _FIELD_KEYWORDS):
        return True
    if _title_has_comparison_markers(title):
        return True
    for _, keywords in _SERVICE_CATEGORIES:
        for keyword in keywords:
            if re.search(_keyword_pattern(keyword), title, flags=re.IGNORECASE):
                return True
    for phrase in _GENERIC_INTEREST_KEYWORDS:
        if re.search(_keyword_pattern(phrase), title, flags=re.IGNORECASE):
            return True
    if _WHICH_DECISION_REGEX.search(title):
        return True
    return False


def _extract_destination(
    title: str, body: str, title_is_comparison_question: bool, suppress_body_entirely: bool = False
) -> tuple:
    """
    Extract the destination, respecting: title over body, and explicit
    multi-country comparisons never collapsing to an arbitrary "first"
    country.

    Returns (destination, is_multi_country_comparison, compared_countries):
      - 2+ distinct countries found in the TITLE -> comparison; destination
        is None rather than arbitrarily picking one.
      - The title poses an explicit comparison question (e.g. "which is
        better X or Y") even with only 0 or 1 recognized country -> also
        None. A single recognized country is just as unreliable here as
        zero — the OTHER option(s) being compared may simply not match
        any of our keywords (e.g. "Monash Malaysia or University of
        Auckland" only recognizes "Malaysia"; picking it would still be
        an arbitrary "only one that happened to match" choice).
      - Otherwise, exactly 1 distinct country in the title -> that's the
        destination, and the body is never consulted (title always wins).
      - 0 countries in the title and no comparison marker: consult the
        body with the same 0/1/2+ rule, unless `suppress_body_entirely`
        is set (the title gave no topical anchor at all, so nothing in
        the body can be trusted to be about the same thing — see
        `_title_has_any_topical_signal`).
    """
    title_countries = _dedupe_labels_in_order(_iter_matches(title, _COUNTRY_KEYWORDS))
    if len(title_countries) >= 2:
        return None, True, title_countries
    if title_is_comparison_question:
        return None, False, []
    if len(title_countries) == 1:
        return title_countries[0], False, title_countries
    if suppress_body_entirely:
        return None, False, []

    body_countries = _dedupe_labels_in_order(_iter_matches(body, _COUNTRY_KEYWORDS))
    if len(body_countries) >= 2:
        return None, True, body_countries
    if len(body_countries) == 1:
        return body_countries[0], False, body_countries
    return None, False, []


def _extract_degree(title: str, body: str, suppress_body_fallback: bool) -> Optional[tuple]:
    """
    Title wins if present; body is consulted only when the title has
    nothing AND the title isn't already a self-contained comparison.

    When the title mentions two distinct degree levels, distinguish:
      - a TRANSITION ("Going from Robotics MS to BME PhD") — the target
        is the LATER-mentioned degree; the earlier one is background,
        mirroring the same current-vs-target principle already applied
        to B.Tech backgrounds (see `_FIELD_KEYWORDS` priority ordering).
      - a PARALLEL target ("Funded MS/PhD in USA") — both are being
        targeted together; represented as a schema-compatible joined
        label ("Masters / PhD"), the same principle used for multi-
        country destinations.
      - otherwise (e.g. "MS abroad, MBA India, or work first" — a
        comparison via commas/"or", no "to"/"/" link between them) —
        unchanged existing behavior: the first-mentioned degree wins.
    """
    title_hits = _iter_matches(title, _DEGREE_KEYWORDS)
    if title_hits:
        distinct_hits = []
        seen_labels = set()
        for pos, label, keyword in title_hits:
            if label not in seen_labels:
                seen_labels.add(label)
                distinct_hits.append((pos, label, keyword))
        if len(distinct_hits) >= 2:
            (pos1, label1, kw1), (pos2, label2, kw2) = distinct_hits[0], distinct_hits[1]
            between = title[pos1 + len(kw1): pos2]
            if re.fullmatch(r"\s*/\s*", between):
                return f"{label1} / {label2}", f"{kw1}/{kw2}"
            if re.search(r"\bto\b", between, flags=re.IGNORECASE):
                return label2, kw2  # the later-mentioned degree is the target
        _, label, keyword = title_hits[0]
        return label, keyword
    if suppress_body_fallback:
        return None
    body_hits = _iter_matches(body, _DEGREE_KEYWORDS)
    if body_hits:
        _, label, keyword = body_hits[0]
        return label, keyword
    return None


def _extract_field(title: str, body: str, suppress_body_fallback: bool) -> Optional[tuple]:
    """Same title-first policy as `_extract_degree`, but priority-ordered
    (see `_first_priority_match`) rather than leftmost-position-ordered,
    so a specific field always beats a generic one within the same zone."""
    title_hit = _first_priority_match(title, _FIELD_KEYWORDS)
    if title_hit:
        return title_hit
    if suppress_body_fallback:
        return None
    return _first_priority_match(body, _FIELD_KEYWORDS)


def _is_resource_sharing_post(combined: str, has_comparison_signal: bool) -> List[str]:
    """
    Return the list of matched resource-sharing/announcement/experience-
    discussion markers if `combined` reads as third-party framing rather
    than a personal ask — empty list otherwise.

    Escaped by either a personal marker/pronoun (handled by the caller
    passing pre-checked text — see `has_personal_marker` usage in
    `classify`) or an explicit comparison/decision signal, since a post
    that poses a genuine comparison ("anyone else planning to apply — I'm
    trying to decide between Germany and France") is a real personal
    question even when it opens with third-party-sounding framing.
    """
    matched = [
        marker for marker in _RESOURCE_SHARING_MARKERS
        if re.search(_keyword_pattern(marker), combined, flags=re.IGNORECASE)
    ]
    if not matched:
        return []
    has_personal_marker = any(
        re.search(_keyword_pattern(marker), combined, flags=re.IGNORECASE)
        for marker in _PERSONAL_MARKERS
    )
    if has_personal_marker or has_comparison_signal:
        return []
    return matched


def _compose_course(degree_label: Optional[str], field_label: Optional[str]) -> Optional[str]:
    """Combine a degree level and a field of study into one course string."""
    if degree_label and field_label:
        return f"{degree_label} {field_label}"
    if degree_label:
        return degree_label
    if field_label:
        return field_label
    return None


class MockAIClassifier:
    """
    Deterministic, keyword/rule-based stand-in for `AIClassifier`.

    Same public interface (`classify(post) -> LeadAnalysis`) and the same
    `LeadAnalysis` schema as the real OpenAI-backed classifier, so it is a
    drop-in replacement for development/testing (AI_PROVIDER=mock). Never
    imports or calls the OpenAI SDK. Purely a test aid — not a substitute
    for real classification quality.
    """

    def classify(self, post: RedditPost) -> LeadAnalysis:
        """
        Classify a single post using fixed keyword rules only, applied to
        the post's own text. Deterministic: the same post always produces
        the same LeadAnalysis.
        """
        title_lower = post.title.lower()
        body_lower = post.post_text.lower()
        combined = f"{title_lower} {body_lower}"

        non_lead_matches = [
            kw for kw in _NON_LEAD_SIGNAL_KEYWORDS
            if re.search(_keyword_pattern(kw), combined, flags=re.IGNORECASE)
        ]
        vague_plea_matches = [
            kw for kw in _VAGUE_PLEA_MARKERS
            if re.search(_keyword_pattern(kw), combined, flags=re.IGNORECASE)
        ]

        # Whether the TITLE gives any real anchor at all. A title with
        # nothing ("Please tell me your opinion") must not let unrelated
        # body content populate destination/degree/field/service — that's
        # exactly how five unrelated countries got hallucinated from body
        # text into a post whose title said nothing about any of them.
        title_has_anchor = _title_has_any_topical_signal(title_lower)

        title_is_comparison = _title_has_comparison_markers(title_lower)
        destination, is_comparison, compared_countries = _extract_destination(
            title_lower, body_lower, title_is_comparison, suppress_body_entirely=not title_has_anchor
        )
        # A comparison-flavored title, OR a title with no topical anchor
        # at all, must not fall back to the body for degree/field either —
        # in both cases, content appearing later in the body cannot be
        # trusted to actually be about the same thing the title asked.
        suppress_body_fallback = title_is_comparison or is_comparison or not title_has_anchor
        degree_hit = _extract_degree(title_lower, body_lower, suppress_body_fallback)
        field_hit = _extract_field(title_lower, body_lower, suppress_body_fallback)

        if is_comparison:
            # Schema-compatible multi-value representation — the
            # destination field stays a single string, but never
            # arbitrarily collapses an explicit comparison to "the first"
            # of several countries the poster is actually weighing.
            destination = " / ".join(compared_countries)

        # Services are only read from the body when the title gave a real
        # anchor to begin with — same reasoning as the extraction
        # suppression above, applied to service_needed (this is what
        # stops "Please tell me your opinion" from acquiring an
        # "Application Guidance" service pulled from unrelated body text).
        service_scan_text = combined if title_has_anchor else title_lower
        matched_services: List[tuple] = []
        seen_service_labels = set()
        for label, keywords in _SERVICE_CATEGORIES:
            for keyword in keywords:
                if re.search(_keyword_pattern(keyword), service_scan_text, flags=re.IGNORECASE):
                    if label not in seen_service_labels:
                        seen_service_labels.add(label)
                        matched_services.append((label, keyword))
                    break

        generic_hits = [
            phrase for phrase in _GENERIC_INTEREST_KEYWORDS
            if re.search(_keyword_pattern(phrase), combined, flags=re.IGNORECASE)
        ]
        if _WHICH_DECISION_REGEX.search(combined) and not any(
            hit.startswith("which") for hit in generic_hits
        ):
            generic_hits.append("which-based decision question")

        degree_label = degree_hit[0] if degree_hit else None
        field_label = field_hit[0] if field_hit else None
        course = _compose_course(degree_label, field_label)

        has_comparison_signal = is_comparison or bool(generic_hits)
        has_service_signal = bool(matched_services)

        has_personal_marker = any(
            re.search(_keyword_pattern(marker), combined, flags=re.IGNORECASE)
            for marker in _PERSONAL_MARKERS
        )
        has_bare_pronoun = any(
            re.search(_keyword_pattern(marker), combined, flags=re.IGNORECASE)
            for marker in _BARE_PRONOUN_MARKERS
        )
        urgency_present = any(
            re.search(_keyword_pattern(marker), combined, flags=re.IGNORECASE)
            for marker in _URGENCY_MARKERS
        )
        has_request_framing = (
            has_personal_marker
            or has_bare_pronoun
            or urgency_present  # "stuck"/"zero availability" inherently imply one's own situation
            or "?" in combined
            or any(
                re.search(_keyword_pattern(marker), combined, flags=re.IGNORECASE)
                for marker in _REQUEST_FRAMING_MARKERS
            )
        )

        # A specific DEGREE is substantial on its own — naming "MBA"/"PhD"
        # in a Reddit title is inherently about the poster's own plan. A
        # bare FIELD with no degree ("Best business majors", "How good
        # are universities in Germany for CS?") is far more likely to be
        # generic discussion, so it additionally needs a personal marker,
        # bare pronoun, or comparison/decision signal to count.
        has_field_only_signal = bool(field_hit) and not degree_hit
        has_course_signal = bool(degree_hit) or (
            has_field_only_signal
            and (has_personal_marker or has_bare_pronoun or has_comparison_signal)
        )

        # Course/degree mentions and explicit comparisons are substantial
        # on their own — a Reddit post naming a specific degree or posing a
        # comparison is inherently about the poster's own plan. A bare
        # service-category keyword (visa/scholarship/etc.) by itself is
        # NOT enough, though: without any sign the poster is asking about
        # their own situation, that's exactly the shape of a news
        # headline ("Visa rules are changing across Europe this year"),
        # not a lead.
        has_specific_substance = (
            has_course_signal
            or has_comparison_signal
            or (has_service_signal and has_request_framing)
        )

        # A general/hypothetical question about a norm or rule ("Are
        # publications a MUST when applying...", "Does Bachelor Grade
        # matter...", "Best business majors") is not a personal ask just
        # because it names a real degree/service and ends in "?" — unless
        # a personal marker, bare pronoun, or comparison/decision signal
        # shows this is actually about the poster's own situation (the
        # personal version of the same question, "Are MY publications
        # enough for MY application?", is not caught here).
        general_question_matches = [
            kw for kw in _GENERAL_QUESTION_MARKERS
            if re.search(_keyword_pattern(kw), combined, flags=re.IGNORECASE)
        ]
        if _GENERAL_NORM_QUESTION_REGEX.search(combined):
            general_question_matches.append("does ... matter")
        is_general_question_only = bool(general_question_matches) and not (
            has_personal_marker or has_bare_pronoun or has_comparison_signal
        )

        # Third-party/experience/announcement framing ("anyone else...",
        # "Announcement: Beware of...", "job market reality") is not a
        # personal ask, unless a personal marker or comparison/decision
        # signal shows the poster is also asking about their own plan.
        resource_sharing_matches = _is_resource_sharing_post(combined, has_comparison_signal)
        if resource_sharing_matches and (has_personal_marker or has_bare_pronoun):
            resource_sharing_matches = []

        # A generic plea with NO specific detail is ambiguous content, not
        # a lead — per the decision hierarchy, ambiguous content should
        # not default to being classified as one.
        is_vague_plea_only = bool(vague_plea_matches) and not has_specific_substance
        is_override = (
            bool(non_lead_matches)
            or bool(resource_sharing_matches)
            or is_vague_plea_only
            or is_general_question_only
        )

        is_lead = has_specific_substance and not is_override

        # A post that isn't a lead isn't "needing" any service, targeting
        # any destination, or pursuing any course either — e.g. "Best
        # business majors" matching the field keyword "business" must not
        # come out reporting course="Business" once we've already decided
        # this isn't a personal lead. "Unknown is better than fabricated"
        # applies to the whole record once is_lead is False, not just
        # service_needed.
        service_needed = [label for label, _ in matched_services] if is_lead else []
        if not is_lead:
            destination = None
            course = None

        if not is_lead:
            intent: IntentLevel = "none"
            if resource_sharing_matches:
                confidence = round(max(0.05, 0.5 - 0.1 * len(resource_sharing_matches)), 2)
                reason = (
                    "Mock classifier: informational/resource-sharing or announcement post, "
                    f"not a personal request (matched: {', '.join(dict.fromkeys(resource_sharing_matches))})."
                )
            elif non_lead_matches:
                confidence = round(max(0.05, 0.5 - 0.1 * len(non_lead_matches)), 2)
                reason = (
                    "Mock classifier: no personal study-abroad intent detected "
                    f"(non-lead signals: {', '.join(dict.fromkeys(non_lead_matches))})."
                )
            elif is_vague_plea_only:
                confidence = 0.2
                reason = (
                    "Mock classifier: generic plea for help with no specific study-abroad/"
                    f"admissions detail (matched: {', '.join(dict.fromkeys(vague_plea_matches))})."
                )
            elif is_general_question_only:
                confidence = 0.3
                reason = (
                    "Mock classifier: general/hypothetical question about a rule or "
                    f"requirement, not a personal request (matched: {', '.join(dict.fromkeys(general_question_matches))})."
                )
            else:
                confidence = 0.5
                reason = "Mock classifier: no study-abroad/admissions signals found in this post."
        else:
            has_high_intent = (
                any(phrase in combined for phrase in _HIGH_INTENT_PHRASES)
                or "Counselling" in service_needed
                or (has_service_signal and urgency_present)
            )
            has_medium_intent = (
                any(phrase in combined for phrase in _MEDIUM_INTENT_PHRASES)
                or bool(generic_hits)
                or is_comparison
                or (degree_label is not None and field_label is not None)
            )
            if has_high_intent:
                intent = "high"
            elif has_medium_intent:
                intent = "medium"
            else:
                intent = "low"

            signal_count = sum(
                [
                    bool(destination),
                    is_comparison,
                    bool(degree_hit),
                    bool(field_hit),
                    len(matched_services) > 0,
                    bool(generic_hits),
                ]
            )
            confidence = round(min(0.95, 0.5 + 0.08 * signal_count), 2)

            reason_terms: List[str] = []
            if is_comparison:
                reason_terms.append(f"comparing {', '.join(compared_countries)}")
            elif destination:
                reason_terms.append(destination)
            if degree_label:
                reason_terms.append(degree_label.lower())
            if field_label:
                reason_terms.append(field_label.lower())
            for _, keyword in matched_services:
                reason_terms.append(keyword)
            reason_terms.extend(generic_hits)
            deduped_terms = list(dict.fromkeys(reason_terms))  # preserve order, drop dupes
            reason = "Mock classifier matched signals: " + ", ".join(deduped_terms) + "."

        result = LeadAnalysis(
            is_lead=is_lead,
            intent=intent,
            destination=destination,
            course=course,
            service_needed=service_needed,
            reason=reason,
            confidence=confidence,
        )

        logger.info("Mock AI classification completed for post %s", post.reddit_post_id)
        return result


# Type used purely for annotations in app/main.py — both classifiers share
# the same `classify(post) -> LeadAnalysis` interface.
AnyAIClassifier = Union[AIClassifier, MockAIClassifier]


def create_ai_classifier(provider: str, api_key: str, model: str) -> AnyAIClassifier:
    """
    Build the configured AI classifier without changing call sites in
    app/main.py beyond the single instantiation call.

    provider="openai" (default, backward compatible) returns the real
    OpenAI-backed AIClassifier. provider="mock" returns MockAIClassifier
    and never touches the OpenAI SDK — `api_key`/`model` are ignored in
    that case.
    """
    if provider == "mock":
        logger.info("AI provider: mock")
        return MockAIClassifier()

    logger.info("AI provider: openai (model=%s)", model)
    return AIClassifier(api_key=api_key, model=model)
