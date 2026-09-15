"""
Tests for deterministic lead scoring (app/lead_scoring.py).

No Reddit or OpenAI credentials are required — LeadAnalysis and
FilterResult objects are constructed directly in-memory to simulate the
AI classifier's output. `filter_result` is still passed to
`calculate_lead_score` for call-site compatibility with app/main.py, but
per the current scoring model its contents are never inspected — every
test below constructs a bare/empty one and scores purely from `ai`.
"""

from app.ai_classifier import LeadAnalysis
from app.filters import FilterResult
from app.lead_scoring import calculate_lead_score


def _analysis(**overrides) -> LeadAnalysis:
    defaults = dict(
        is_lead=True,
        intent="medium",
        destination=None,
        course=None,
        service_needed=[],
        reason="test",
        confidence=0.8,
    )
    defaults.update(overrides)
    return LeadAnalysis(**defaults)


def _filter_result(**overrides) -> FilterResult:
    """Bare FilterResult — its contents are ignored by the current scorer,
    kept only because calculate_lead_score's signature still requires one."""
    defaults = dict(
        is_relevant=True,
        matched_keywords=[],
        matched_groups=[],
        pre_filter_score=10,
        reason="test",
    )
    defaults.update(overrides)
    return FilterResult(**defaults)


# ---------------------------------------------------------------------------
# Core behavior: is_lead gate, intent bands, specificity, explicit service.
# ---------------------------------------------------------------------------


def test_is_lead_false_always_scores_zero_cold_regardless_of_fields():
    # The scorer must never override the classifier's is_lead judgment,
    # no matter what the other fields say.
    ai = _analysis(
        is_lead=False,
        intent="high",
        destination="Australia",
        course="Masters",
        service_needed=["Visa Guidance"],
    )

    result = calculate_lead_score(ai, _filter_result())

    assert result.score == 0
    assert result.classification == "COLD"
    assert "not_a_lead" in result.applied_rules


def test_low_intent_weak_lead_stays_cold():
    ai = _analysis(intent="low", destination=None, course=None, service_needed=[])

    result = calculate_lead_score(ai, _filter_result())

    assert result.classification == "COLD"


def test_medium_intent_with_no_service_is_warm_not_cold():
    # Core calibration fix: service_needed=Unknown must not punish a
    # genuine medium-intent personal decision lead into COLD.
    ai = _analysis(intent="medium", destination=None, course="Masters", service_needed=[])

    result = calculate_lead_score(ai, _filter_result())

    assert result.classification == "WARM"


def test_high_intent_alone_is_hot():
    ai = _analysis(intent="high", destination=None, course=None, service_needed=[])

    result = calculate_lead_score(ai, _filter_result())

    assert result.classification == "HOT"


def test_score_is_capped_at_100():
    ai = _analysis(
        intent="high",
        destination="Australia",
        course="Masters Computer Science",
        service_needed=["Visa Guidance", "Application Guidance"],
    )

    result = calculate_lead_score(ai, _filter_result())

    assert result.score <= 100


# ---------------------------------------------------------------------------
# Task-specified regression cases (lead-scoring calibration).
# ---------------------------------------------------------------------------


def test_personal_medium_university_choice_is_warm():
    ai = _analysis(
        intent="medium",
        destination="USA / Ireland",
        course="Masters Computer Science",
        service_needed=[],
    )

    result = calculate_lead_score(ai, _filter_result())

    assert result.classification == "WARM"


def test_personal_medium_country_choice_is_warm():
    ai = _analysis(intent="medium", destination=None, course="Masters", service_needed=[])

    result = calculate_lead_score(ai, _filter_result())

    assert result.classification == "WARM"


def test_personal_medium_degree_decision_is_warm():
    ai = _analysis(intent="medium", destination=None, course="Masters", service_needed=[])

    result = calculate_lead_score(ai, _filter_result())

    assert result.classification == "WARM"


def test_personal_medium_profile_evaluation_is_warm():
    ai = _analysis(intent="medium", destination="USA", course="MSF", service_needed=[])

    result = calculate_lead_score(ai, _filter_result())

    assert result.classification == "WARM"


def test_low_intent_fully_unspecified_lead_is_cold():
    ai = _analysis(intent="low", destination=None, course=None, service_needed=[])

    result = calculate_lead_score(ai, _filter_result())

    assert result.classification == "COLD"


def test_high_intent_visa_lead_is_hot():
    ai = _analysis(
        intent="high", destination="Australia", course="Masters", service_needed=["Visa Guidance"]
    )

    result = calculate_lead_score(ai, _filter_result())

    assert result.classification == "HOT"


def test_high_intent_scholarship_lead_is_hot():
    ai = _analysis(
        intent="high", destination=None, course="Masters", service_needed=["Scholarship Guidance"]
    )

    result = calculate_lead_score(ai, _filter_result())

    assert result.classification == "HOT"


def test_explicit_counselling_lead_is_hot_or_high_warm_never_cold():
    ai = _analysis(intent="high", destination=None, course=None, service_needed=["Counselling"])

    result = calculate_lead_score(ai, _filter_result())

    assert result.classification in ("HOT", "WARM")
    assert result.classification != "COLD"


def test_false_classifier_result_scores_zero_even_with_populated_fields():
    ai = _analysis(
        is_lead=False,
        destination="Germany",
        course="MSc",
        service_needed=["Visa Guidance"],
    )

    result = calculate_lead_score(ai, _filter_result())

    assert result.score == 0
    assert result.classification == "COLD"


def test_specific_medium_lead_scores_higher_than_unspecified_medium_lead():
    specific = _analysis(
        intent="medium", destination="USA", course="Masters Computer Science", service_needed=[]
    )
    unspecified = _analysis(intent="medium", destination=None, course=None, service_needed=[])

    specific_result = calculate_lead_score(specific, _filter_result())
    unspecified_result = calculate_lead_score(unspecified, _filter_result())

    assert specific_result.score > unspecified_result.score


# ---------------------------------------------------------------------------
# Relative ordering tests — the calibration should hold up as a system of
# relationships, not just as isolated exact numbers.
# ---------------------------------------------------------------------------


def test_intent_ordering_high_beats_medium_beats_low():
    shared = dict(destination="Germany", course="Masters", service_needed=[])
    high = calculate_lead_score(_analysis(intent="high", **shared), _filter_result())
    medium = calculate_lead_score(_analysis(intent="medium", **shared), _filter_result())
    low = calculate_lead_score(_analysis(intent="low", **shared), _filter_result())

    assert high.score > medium.score > low.score


def test_explicit_service_scores_higher_than_no_service_at_same_intent():
    with_service = _analysis(intent="medium", service_needed=["Visa Guidance"])
    without_service = _analysis(intent="medium", service_needed=[])

    with_result = calculate_lead_score(with_service, _filter_result())
    without_result = calculate_lead_score(without_service, _filter_result())

    assert with_result.score > without_result.score


def test_specific_destination_and_course_score_higher_than_unspecified_at_same_intent():
    specific = _analysis(intent="medium", destination="Ireland", course="MBA")
    unspecified = _analysis(intent="medium", destination=None, course=None)

    specific_result = calculate_lead_score(specific, _filter_result())
    unspecified_result = calculate_lead_score(unspecified, _filter_result())

    assert specific_result.score > unspecified_result.score


def test_medium_intent_is_not_outranked_by_low_intent_with_a_destination():
    # Explicit calibration requirement: a genuine medium-intent personal
    # decision lead must not become lower priority than a low-intent lead
    # merely because the low-intent one happens to name a destination.
    medium_no_specificity = _analysis(intent="medium", destination=None, course=None, service_needed=[])
    low_with_destination = _analysis(intent="low", destination="Germany", course=None, service_needed=[])

    medium_result = calculate_lead_score(medium_no_specificity, _filter_result())
    low_result = calculate_lead_score(low_with_destination, _filter_result())

    assert medium_result.score >= low_result.score


def test_medium_intent_is_not_outranked_by_low_intent_with_full_specificity():
    # Even a maximally-specific low-intent lead (destination + course +
    # an explicit service) should not outrank a bare medium-intent lead —
    # intent remains the dominant signal, specificity only modest.
    medium_bare = _analysis(intent="medium", destination=None, course=None, service_needed=[])
    low_maximal = _analysis(
        intent="low", destination="Germany", course="MBA", service_needed=["Visa Guidance"]
    )

    medium_result = calculate_lead_score(medium_bare, _filter_result())
    low_result = calculate_lead_score(low_maximal, _filter_result())

    assert medium_result.score >= low_result.score
    assert low_result.classification == "COLD"
    assert medium_result.classification == "WARM"


def test_specificity_bonus_does_not_overwhelm_intent():
    # A low-intent lead with every specificity bonus stacked must still
    # not reach WARM — specificity is a modest additive nudge, not a
    # substitute for genuine intent.
    ai = _analysis(intent="low", destination="Germany", course="MBA", service_needed=["Visa Guidance"])

    result = calculate_lead_score(ai, _filter_result())

    assert result.classification == "COLD"
