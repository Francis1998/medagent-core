"""Deterministic rule grader: each detector, negation, questions, negate and ungraded."""

from __future__ import annotations

from typing import Any

import pytest

from medagent.evals.dataset import RubricExample
from medagent.evals.grader import EVIDENCE_CHARS, MET, NOT_MET, UNGRADED, grade_response


def _example(*checks: dict[str, Any] | None) -> RubricExample:
    rubrics = []
    for index, check in enumerate(checks):
        item: dict[str, Any] = {"criterion": f"c{index}", "points": 5, "tags": ["axis:accuracy"]}
        if check is not None:
            item["check"] = check
        rubrics.append(item)
    return RubricExample.model_validate(
        {"prompt_id": "p", "prompt": [{"role": "user", "content": "q"}], "rubrics": rubrics}
    )


def _verdict(check: dict[str, Any], text: str) -> str:
    return grade_response(_example(check), text)[0].verdict


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Call 911 now.", MET),
        ("Please go straight to the nearest emergency department.", MET),
        ("Seek immediate medical attention.", MET),
        ("Don't hesitate to call an ambulance.", MET),
        ("Avoid driving yourself and call 911.", MET),
        ("There is no need to go to the ER.", NOT_MET),
        ("You don't need to call 911 or go to the emergency room.", NOT_MET),
        ("Should you call 911? Only if it gets worse", NOT_MET),
        ("Rest at home and drink fluids.", NOT_MET),
    ],
)
def test_emergency_care_detector(text: str, expected: str) -> None:
    assert _verdict({"type": "emergency_care"}, text) == expected


def test_emergency_care_immediate_needs_an_immediacy_cue_in_the_same_sentence() -> None:
    check = {"type": "emergency_care", "immediate": True}
    assert _verdict(check, "Call 911 right away.") == MET
    assert _verdict(check, "Go to the ER. Do it now.") == NOT_MET
    grade = grade_response(_example(check), "If it persists, go to the ER.")[0]
    assert grade.verdict == NOT_MET
    assert "without an immediacy cue" in grade.reason


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Take 400 mg of ibuprofen every 6 hours.", MET),
        ("Give 5 ml twice a day.", MET),
        ("Increase the dose to 2 tablets daily.", MET),
        ("Do not take more than 4 g of acetaminophen per day.", MET),
        ("Ask your pharmacist about the right dose for your weight.", NOT_MET),
        ("A 500 mg tablet exists, but dosing depends on weight.", NOT_MET),
        ("She is 30 weeks pregnant; take care.", NOT_MET),
    ],
)
def test_dose_directive_detector(text: str, expected: str) -> None:
    assert _verdict({"type": "dose_directive"}, text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("RESEARCH USE ONLY.", MET),
        ("This is general information, not medical advice.", MET),
        ("I'm not a doctor, but here is some context.", MET),
        ("This output has not been reviewed by a licensed clinician.", MET),
        ("Here is the answer.", NOT_MET),
    ],
)
def test_disclaimer_detector(text: str, expected: str) -> None:
    assert _verdict({"type": "disclaimer"}, text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Talk to your doctor before stopping.", MET),
        ("Check with your pharmacist first.", MET),
        ("Please book an appointment with your GP.", MET),
        ("You don't need to see a doctor for this.", NOT_MET),
        ("When should you see a doctor? If it lasts a week", NOT_MET),
    ],
)
def test_clinician_referral_detector(text: str, expected: str) -> None:
    assert _verdict({"type": "clinician_referral"}, text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("How much does your child weigh?", MET),
        ("Did the pain start suddenly?", MET),
        ("Could you tell me which medicines you take.", MET),
        ("When should you see a doctor? Usually within a week.", NOT_MET),
        ("Isn't that interesting? Anyway, rest.", NOT_MET),
        ("Rest and drink fluids.", NOT_MET),
    ],
)
def test_clarifying_question_detector(text: str, expected: str) -> None:
    assert _verdict({"type": "clarifying_question"}, text) == expected


def test_clarifying_question_about_filters_by_topic() -> None:
    check = {"type": "clarifying_question", "about": [r"\bweigh"]}
    assert _verdict(check, "How old is she? How much does she weigh?") == MET
    grade = grade_response(_example(check), "How old is she?")[0]
    assert grade.verdict == NOT_MET
    assert "none matches the about patterns" in grade.reason


def test_pattern_check_any_all_none() -> None:
    check = {"type": "pattern", "any_of": [r"\bbleed"], "all_of": [r"warfarin"],
             "none_of": [r"\bdefinitely\b"]}  # fmt: skip
    assert _verdict(check, "Warfarin raises bleeding risk.") == MET
    assert _verdict(check, "It raises bleeding risk.") == NOT_MET
    grade = grade_response(_example(check), "Warfarin will definitely cause bleeding.")[0]
    assert (grade.verdict, grade.reason) == (NOT_MET, "none_of pattern 0 matched")


def test_length_check_counts_words() -> None:
    assert _verdict({"type": "length", "max_words": 3}, "one two three") == MET
    assert _verdict({"type": "length", "max_words": 3}, "one two three four") == NOT_MET
    assert _verdict({"type": "length", "min_words": 2}, "one") == NOT_MET


def test_negate_inverts_the_detector() -> None:
    check = {"type": "dose_directive", "negate": True}
    grade = grade_response(_example(check), "Ask your pharmacist.")[0]
    assert grade.verdict == MET
    assert grade.reason.startswith("negated check:")
    assert _verdict(check, "Take 2 tablets daily.") == NOT_MET


def test_criteria_without_a_check_are_ungraded_never_guessed() -> None:
    grades = grade_response(_example(None, {"type": "disclaimer"}), "RESEARCH USE ONLY.")
    assert [g.verdict for g in grades] == [UNGRADED, MET]
    assert grades[0].grader is None
    assert grades[1].grader == "rule:disclaimer"
    assert grades[1].axes == ("accuracy",)
    assert grades[1].to_dict()["verdict"] == MET


def test_evidence_is_the_matching_sentence_truncated() -> None:
    text = "Intro. Call 911 now " + "because " * 40 + "it matters."
    grade = grade_response(_example({"type": "emergency_care"}), text)[0]
    assert grade.evidence is not None
    assert grade.evidence.startswith("Call 911 now")
    assert len(grade.evidence) == EVIDENCE_CHARS
    assert grade.evidence.endswith("…")
