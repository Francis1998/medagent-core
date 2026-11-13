"""Validation of trial definitions (trial-criteria format 1.0) and screening arguments."""

from __future__ import annotations

from typing import Any

import pytest

from medagent.trials.criteria import TrialInputError
from medagent.trials.screening import screen_trials_request
from tests.unit.trials.builders import EGFR, bundle, lab, trial

CANARY = "CANARY-VALUE-9931"


def _rejects(arguments: dict[str, Any]) -> TrialInputError:
    with pytest.raises(TrialInputError) as exc_info:
        screen_trials_request(arguments)
    assert CANARY not in str(exc_info.value)
    return exc_info.value


def _with(criterion: dict[str, Any], *, section: str = "inclusion") -> dict[str, Any]:
    definition = trial(criterion) if section == "inclusion" else trial(exclusion=(criterion,))
    return {"bundle": bundle(), "trials": [definition]}


@pytest.mark.parametrize(
    ("criterion", "message"),
    [
        (
            {
                "id": "c",
                "type": "condition",
                "text": "t",
                "codes": [{"system": "s", "code": "1"}],
                "operator": ">=",
            },
            "trials[0].inclusion[0] (type condition) does not accept: operator.",
        ),
        (
            {"id": "c", "type": "condition", "text": "t"},
            "(type condition) needs codes and/or terms.",
        ),
        (
            {"id": "m", "type": "medication", "text": "t"},
            "needs ingredients, classes and/or rxnorm_codes.",
        ),
        (
            {"id": "m", "type": "medication", "text": "t", "ingredients": ["--"]},
            "ingredients must contain letters",
        ),
        ({**lab(), "unit": CANARY}, "trials[0].inclusion[0].unit is not a supported unit"),
        (
            {k: v for k, v in lab().items() if k != "unit"},
            "(type lab) needs a unit, or relative_to.",
        ),
        (
            {**lab(), "relative_to": "uln"},
            "with relative_to compares multiples of the limit and takes no unit.",
        ),
        (
            {**lab(operator="between", value=None), "low": 1},
            "(operator between) needs low and high, and no value.",
        ),
        (
            {**lab(operator="between", value=None), "low": 9, "high": 1},
            "has low greater than high.",
        ),
        ({**lab(), "low": 1}, "(operator >=) needs a value, and no low or high."),
        (
            {**lab(), "codes": [{**EGFR, "match": "prefix"}]},
            "'prefix' is only allowed for conditions.",
        ),
        (
            {**lab(), "id": "eligibility.sex"},
            "must not start with the reserved prefix 'eligibility.'",
        ),
        (
            {"id": "p", "type": "pregnancy", "text": "t", "terms": ["pregnant"]},
            "(type pregnancy) does not accept: terms.",
        ),
        (
            {"id": "f", "type": "free_text", "text": "t", "presence": "absent"},
            "(type free_text) does not accept: presence.",
        ),
    ],
)
def test_semantic_rules_the_schema_cannot_express(criterion: dict[str, Any], message: str) -> None:
    error = _rejects(_with(criterion))

    assert error.reason == "invalid_trial"
    assert message in str(error)


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"bundle": bundle()}, "Invalid arguments: arguments.trials is required"),
        ({"bundle": bundle(), "trials": []}, "arguments.trials must contain at least 1 item(s)"),
        (
            {"bundle": bundle(), "trials": [{**trial(lab()), "schema_version": "2.0"}]},
            "arguments.trials[0].schema_version must be one of ['1.0']",
        ),
        (
            {"bundle": bundle(), "trials": [trial({**lab(), "operator": "~"})]},
            "arguments.trials[0].inclusion[0].operator must be one of",
        ),
        (
            {"bundle": bundle(), "trials": [trial(lab(), module={"minimumAge": "18 yrs"})]},
            "arguments.trials[0].eligibilityModule.minimumAge must match pattern",
        ),
        (
            {"bundle": bundle(), "trials": [trial(lab())], "patient_context": {"name": CANARY}},
            "arguments.patient_context has unexpected properties "
            "(allowed: breastfeeding, pregnant)",
        ),
        (
            {"bundle": bundle(), "trials": [trial(lab())], "as_of": "2026-02-30"},
            "as_of must be a valid",
        ),
        (
            {"bundle": bundle(), "trials": [trial(lab())], "as_of": "2026-11-12\n"},
            "as_of must be a date",
        ),
        ({"bundle": {"resourceType": "Patient"}, "trials": [trial(lab())]}, "must equal 'Bundle'"),
    ],
)
def test_invalid_arguments_name_paths_never_values(arguments: dict[str, Any], message: str) -> None:
    error = _rejects(arguments)

    assert message in str(error)


def test_trial_and_criterion_ids_must_be_unique() -> None:
    duplicate_criteria = trial(lab("x"), exclusion=(lab("x"),))
    error = _rejects({"bundle": bundle(), "trials": [duplicate_criteria]})
    assert "duplicate criterion ids" in str(error)

    error = _rejects({"bundle": bundle(), "trials": [trial(lab()), trial(lab())]})
    assert error.reason == "duplicate_trial"


def test_trial_ids_reject_a_trailing_newline_the_schema_regex_allows() -> None:
    definition = {**trial(lab()), "trial_id": "TEST-001\n"}

    error = _rejects({"bundle": bundle(), "trials": [definition]})

    assert "trials[0].trial_id must match the id pattern." in str(error)


def test_a_trial_needs_something_to_evaluate() -> None:
    error = _rejects({"bundle": bundle(), "trials": [trial(module={"sex": "ALL"})]})

    assert error.reason == "empty_trial"


def test_minimum_age_cannot_exceed_maximum_age() -> None:
    definition = trial(module={"minimumAge": "13 Months", "maximumAge": "1 Year"})

    error = _rejects({"bundle": bundle(), "trials": [definition]})

    assert "has a minimumAge greater than its maximumAge." in str(error)


def test_equal_limits_in_different_units_are_accepted() -> None:
    definition = trial(module={"minimumAge": "12 Months", "maximumAge": "1 Year"})

    screening = screen_trials_request(
        {"bundle": bundle(), "trials": [definition], "as_of": "2026-11-12"}
    )

    assert [c["criterion_id"] for c in screening.structured()["trials"][0]["criteria"]] == [
        "eligibility.minimum_age",
        "eligibility.maximum_age",
    ]
