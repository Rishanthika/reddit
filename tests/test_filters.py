"""
Tests for the keyword pre-filter (app/filters.py).

No Reddit or OpenAI credentials are required — RedditPost objects are
constructed directly in-memory.
"""

from datetime import datetime, timezone

from app.filters import filter_post
from app.reddit_client import RedditPost


def _make_post(title: str, body: str = "") -> RedditPost:
    return RedditPost(
        reddit_post_id="test123",
        username="u/tester",
        subreddit="studyabroad",
        title=title,
        post_url="https://reddit.com/r/studyabroad/comments/test123",
        post_text=body,
        created_at=datetime.now(timezone.utc),
    )


def test_ms_in_germany_is_relevant():
    post = _make_post("I want to do MS in Germany")
    result = filter_post(post)
    assert result.is_relevant is True


def test_laptop_question_is_not_relevant():
    post = _make_post("Which laptop should I buy?")
    result = filter_post(post)
    assert result.is_relevant is False


def test_canada_university_help_is_relevant():
    post = _make_post("Need help applying to Canadian universities")
    result = filter_post(post)
    assert result.is_relevant is True


def test_generic_country_mention_is_not_relevant():
    post = _make_post("Germany is beautiful")
    result = filter_post(post)
    assert result.is_relevant is False


def test_ielts_for_uk_masters_is_relevant():
    post = _make_post("IELTS score required for UK masters?")
    result = filter_post(post)
    assert result.is_relevant is True


def test_generic_college_laptop_is_not_falsely_flagged():
    post = _make_post("What is the best laptop for college?")
    result = filter_post(post)
    assert result.is_relevant is False


def test_standalone_service_keyword_is_relevant():
    post = _make_post("Can anyone recommend a good consultant?")
    result = filter_post(post)
    assert result.is_relevant is True


# ---------------------------------------------------------------------------
# Recall-oriented redesign tests.
#
# The pre-filter's job changed from "requires 2+ keyword groups (or one
# strong standalone group)" to "any ONE qualifying group is enough" — its
# only remaining responsibility is stopping content with literally no
# configured signal (or only noise / only a bare country mention) from
# reaching the AI. These tests lock in that new behavior directly against
# the FutureGrad lead-quality review's findings.
# ---------------------------------------------------------------------------


def test_single_intent_signal_passes():
    # Previously rejected: "Only generic/insufficient keyword signal
    # (intent)". A phrase like "study abroad" is specific and on-topic
    # enough on its own to earn an AI classification.
    post = _make_post("Thinking about studying — is study abroad worth it?")
    result = filter_post(post)
    assert result.is_relevant is True
    assert result.matched_groups == ["intent"]


def test_single_admissions_signal_passes():
    # Previously rejected: "Only generic/insufficient keyword signal
    # (admissions)". Someone asking about their own application/admission
    # is squarely FutureGrad's business even with no other signal.
    post = _make_post("My application deadline is approaching, what should I do?")
    result = filter_post(post)
    assert result.is_relevant is True
    assert "admissions" in result.matched_groups


def test_single_course_degree_signal_passes():
    # Previously rejected: "Only generic/insufficient keyword signal
    # (courses)". A bare degree mention, posted in a study-abroad
    # subreddit, is a plausible early-stage lead the AI should evaluate.
    post = _make_post("Is a PhD worth it?")
    result = filter_post(post)
    assert result.is_relevant is True
    assert result.matched_groups == ["courses"]


def test_single_destination_signal_alone_is_still_rejected():
    # By design, "countries" is NOT a qualifying group on its own — a bare
    # country name says nothing about study intent (this is what keeps
    # "Germany is beautiful" correctly rejected). A destination mention
    # only counts once paired with a qualifying group (see
    # test_destination_plus_qualifying_group_passes below).
    post = _make_post("Spain is a beautiful country")
    result = filter_post(post)
    assert result.is_relevant is False
    assert result.matched_groups == ["countries"]


def test_destination_plus_qualifying_group_passes():
    post = _make_post("Is a Master's in Spain a good idea?")
    result = filter_post(post)
    assert result.is_relevant is True
    assert "countries" in result.matched_groups
    assert "courses" in result.matched_groups


def test_zero_keyword_matches_is_rejected():
    post = _make_post("What's everyone's favorite dorm snack?")
    result = filter_post(post)
    assert result.is_relevant is False
    assert result.matched_groups == []


def test_obvious_noise_is_rejected():
    post = _make_post("Which laptop should I buy for college?")
    result = filter_post(post)
    assert result.is_relevant is False


def test_multiple_qualifying_groups_passes():
    post = _make_post("Applying for a Master's in Germany, need advice")
    result = filter_post(post)
    assert result.is_relevant is True
    assert len(result.matched_groups) >= 2


def test_strong_standalone_service_signal_still_passes():
    post = _make_post("Need a consultant for my visa application")
    result = filter_post(post)
    assert result.is_relevant is True
    assert "services" in result.matched_groups


def test_undergraduation_is_recognized():
    # Regression test: the old "undergraduate" keyword did not match the
    # real-world phrasing "undergraduation" at all (diverges before the
    # pluralization). The new "undergrad" stem must catch it.
    post = _make_post("Is undergraduation abroad a good option?")
    result = filter_post(post)
    assert result.is_relevant is True
    assert "courses" in result.matched_groups


def test_spain_japan_sweden_finland_denmark_uae_are_recognized():
    # These countries were entirely missing from the pre-filter's keyword
    # list before this change. Each should now be matched (paired here
    # with a qualifying admissions/course signal so the post also passes).
    countries_and_posts = [
        ("Spain", "Applying to a university in Spain"),
        ("Japan", "Applying to a university in Japan"),
        ("Sweden", "Applying to a university in Sweden"),
        ("Finland", "Applying to a university in Finland"),
        ("Denmark", "Applying to a university in Denmark"),
        ("UAE", "Applying to a university in the UAE"),
    ]
    for country_name, title in countries_and_posts:
        post = _make_post(title)
        result = filter_post(post)
        assert result.is_relevant is True, f"expected {country_name} post to pass"
        assert "countries" in result.matched_groups, f"expected {country_name} to be matched"


def test_new_zealand_still_recognized():
    # Was already present before this change — confirm it wasn't broken.
    post = _make_post("Applying to a university in New Zealand")
    result = filter_post(post)
    assert result.is_relevant is True
    assert "countries" in result.matched_groups
