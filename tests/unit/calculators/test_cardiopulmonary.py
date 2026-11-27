"""Worked examples and boundaries: CURB-65, Wells PE, PERC, CHA2DS2-VASc, HAS-BLED, HEART."""

from __future__ import annotations

from typing import Any

import pytest

from medagent.calculators import run_calculator


def points(result: dict[str, Any], criterion: str) -> float:
    return next(c["points"] for c in result["components"] if c["criterion"] == criterion)


CURB65_BASE: dict[str, Any] = {
    "confusion": False,
    "urea": {"value": 5.0, "unit": "mmol/L"},
    "respiratory_rate": 18,
    "systolic_bp": 120,
    "diastolic_bp": 80,
    "age": 40,
}


def curb65(**changes: Any) -> dict[str, Any]:
    return run_calculator("curb_65", {**CURB65_BASE, **changes})


def test_curb65_worked_example_converts_bun_and_scores_every_criterion() -> None:
    result = curb65(
        confusion=True,
        urea={"value": 26, "unit": "mg/dL"},
        respiratory_rate=32,
        systolic_bp=88,
        diastolic_bp=58,
        age=72,
    )
    assert result["score"] == 5
    assert result["interpretation"]["band"] == "severe"
    assert result["inputs"]["urea"] == {
        "value": 9.282,
        "unit": "mmol/L",
        "reported": {"value": 26, "unit": "mg/dL"},
    }
    assert [c["points"] for c in result["components"]] == [1, 1, 1, 1, 1]
    assert result["components"][1]["rule"] == "urea 9.28 mmol/L > 7: +1"


@pytest.mark.parametrize(
    ("changes", "criterion", "expected"),
    [
        ({"urea": {"value": 7.0, "unit": "mmol/L"}}, "urea_over_7", 0),
        ({"urea": {"value": 7.1, "unit": "mmol/L"}}, "urea_over_7", 1),
        ({"urea": {"value": 19.6, "unit": "mg/dL"}}, "urea_over_7", 0),
        ({"urea": {"value": 19.7, "unit": "mg/dL"}}, "urea_over_7", 1),
        ({"respiratory_rate": 29}, "resp_rate_30_plus", 0),
        ({"respiratory_rate": 30}, "resp_rate_30_plus", 1),
        ({"systolic_bp": 90, "diastolic_bp": 61}, "low_blood_pressure", 0),
        ({"systolic_bp": 89}, "low_blood_pressure", 1),
        ({"diastolic_bp": 60}, "low_blood_pressure", 1),
        ({"age": 64}, "age_65_plus", 0),
        ({"age": 65}, "age_65_plus", 1),
    ],
)
def test_curb65_thresholds(changes: dict[str, Any], criterion: str, expected: int) -> None:
    assert points(curb65(**changes), criterion) == expected


@pytest.mark.parametrize(
    ("changes", "band"),
    [
        ({"age": 70}, "mild"),
        ({"age": 70, "confusion": True}, "moderate"),
        ({"age": 70, "confusion": True, "respiratory_rate": 30}, "severe"),
    ],
)
def test_curb65_bands(changes: dict[str, Any], band: str) -> None:
    assert curb65(**changes)["interpretation"]["band"] == band


WELLS_BASE = {
    "clinical_dvt_signs": False,
    "pe_most_likely_diagnosis": False,
    "heart_rate": 80,
    "immobilization_or_recent_surgery": False,
    "previous_dvt_or_pe": False,
    "hemoptysis": False,
    "malignancy": False,
}


@pytest.mark.parametrize(
    ("changes", "score", "band", "two_tier"),
    [
        ({}, 0, "low", "pe_unlikely"),
        ({"heart_rate": 100}, 0, "low", "pe_unlikely"),
        ({"heart_rate": 101}, 1.5, "low", "pe_unlikely"),
        ({"hemoptysis": True, "malignancy": True}, 2, "moderate", "pe_unlikely"),
        ({"clinical_dvt_signs": True, "malignancy": True}, 4, "moderate", "pe_unlikely"),
        ({"clinical_dvt_signs": True, "previous_dvt_or_pe": True}, 4.5, "moderate", "pe_likely"),
        # Wells 2000: 6.0 is the top of the moderate band (the fixed scorer bug).
        (
            {"clinical_dvt_signs": True, "pe_most_likely_diagnosis": True},
            6,
            "moderate",
            "pe_likely",
        ),
        (
            {"clinical_dvt_signs": True, "pe_most_likely_diagnosis": True, "heart_rate": 110},
            7.5,
            "high",
            "pe_likely",
        ),
    ],
)
def test_wells_pe(changes: dict[str, Any], score: float, band: str, two_tier: str) -> None:
    result = run_calculator("wells_pe", {**WELLS_BASE, **changes})
    assert result["score"] == score
    assert result["interpretation"]["band"] == band
    assert result["details"]["two_tier"] == two_tier


PERC_BASE = {
    "age": 49,
    "heart_rate": 99,
    "oxygen_saturation": 95,
    "unilateral_leg_swelling": False,
    "hemoptysis": False,
    "recent_surgery_or_trauma": False,
    "prior_pe_or_dvt": False,
    "hormone_use": False,
}


@pytest.mark.parametrize(
    ("changes", "band"),
    [
        ({}, "perc_negative"),
        ({"age": 50}, "perc_positive"),
        ({"heart_rate": 100}, "perc_positive"),
        ({"oxygen_saturation": 94}, "perc_positive"),
        ({"hormone_use": True}, "perc_positive"),
    ],
)
def test_perc_boundaries(changes: dict[str, Any], band: str) -> None:
    assert run_calculator("perc", {**PERC_BASE, **changes})["interpretation"]["band"] == band


CHA2DS2_BASE = {
    "age": 50,
    "sex": "male",
    "congestive_heart_failure": False,
    "hypertension": False,
    "diabetes": False,
    "stroke_tia_thromboembolism": False,
    "vascular_disease": False,
}


@pytest.mark.parametrize(
    ("changes", "score", "band"),
    [
        ({}, 0, "low"),
        ({"sex": "female"}, 1, "moderate"),
        ({"age": 64}, 0, "low"),
        ({"age": 65}, 1, "moderate"),
        ({"age": 74}, 1, "moderate"),
        ({"age": 75}, 2, "high"),
        # 72-year-old woman with hypertension and diabetes: A 1 + Sc 1 + H 1 + D 1.
        ({"age": 72, "sex": "female", "hypertension": True, "diabetes": True}, 4, "high"),
        ({"stroke_tia_thromboembolism": True}, 2, "high"),
    ],
)
def test_cha2ds2_vasc(changes: dict[str, Any], score: int, band: str) -> None:
    result = run_calculator("cha2ds2_vasc", {**CHA2DS2_BASE, **changes})
    assert (result["score"], result["interpretation"]["band"]) == (score, band)


HAS_BLED_BASE = {
    "age": 60,
    "uncontrolled_hypertension": False,
    "abnormal_renal_function": False,
    "abnormal_liver_function": False,
    "stroke_history": False,
    "bleeding_history": False,
    "labile_inr": False,
    "antiplatelet_or_nsaid": False,
    "alcohol_excess": False,
}


@pytest.mark.parametrize(
    ("changes", "score", "band"),
    [
        ({"age": 65}, 0, "low"),
        ({"age": 66}, 1, "low"),
        ({"age": 66, "antiplatelet_or_nsaid": True}, 2, "moderate"),
        ({"age": 70, "uncontrolled_hypertension": True, "antiplatelet_or_nsaid": True}, 3, "high"),
    ],
)
def test_has_bled(changes: dict[str, Any], score: int, band: str) -> None:
    result = run_calculator("has_bled", {**HAS_BLED_BASE, **changes})
    assert (result["score"], result["interpretation"]["band"]) == (score, band)


HEART_BASE: dict[str, Any] = {
    "history": "slightly_suspicious",
    "ecg": "normal",
    "age": 40,
    "hypercholesterolemia": False,
    "hypertension": False,
    "diabetes": False,
    "smoking": False,
    "family_history": False,
    "obesity": False,
    "atherosclerotic_disease": False,
    "troponin": 10,
    "troponin_uln": 14,
}


@pytest.mark.parametrize(
    ("changes", "criterion", "expected"),
    [
        ({"age": 44}, "age", 0),
        ({"age": 45}, "age", 1),
        ({"age": 64}, "age", 1),
        ({"age": 65}, "age", 2),
        ({"troponin": 14}, "troponin", 0),
        ({"troponin": 15}, "troponin", 1),
        ({"troponin": 42}, "troponin", 1),
        ({"troponin": 43}, "troponin", 2),
        ({"hypertension": True, "diabetes": True}, "risk_factors", 1),
        ({"hypertension": True, "diabetes": True, "obesity": True}, "risk_factors", 2),
        ({"atherosclerotic_disease": True}, "risk_factors", 2),
        ({"ecg": "significant_st_deviation"}, "ecg", 2),
    ],
)
def test_heart_criteria(changes: dict[str, Any], criterion: str, expected: int) -> None:
    result = run_calculator("heart", {**HEART_BASE, **changes})
    assert points(result, criterion) == expected


@pytest.mark.parametrize(
    ("changes", "score", "band"),
    [
        ({}, 0, "low"),
        ({"history": "moderately_suspicious", "age": 58, "hypertension": True}, 3, "low"),
        (
            {"history": "moderately_suspicious", "age": 58, "hypertension": True, "troponin": 20},
            4,
            "moderate",
        ),
        (
            {"history": "highly_suspicious", "ecg": "nonspecific_repolarization", "age": 70},
            5,
            "moderate",
        ),
        (
            {
                "history": "highly_suspicious",
                "ecg": "significant_st_deviation",
                "age": 70,
                "atherosclerotic_disease": True,
                "troponin": 50,
            },
            10,
            "high",
        ),
    ],
)
def test_heart_bands(changes: dict[str, Any], score: int, band: str) -> None:
    result = run_calculator("heart", {**HEART_BASE, **changes})
    assert (result["score"], result["interpretation"]["band"]) == (score, band)
