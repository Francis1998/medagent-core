"""Worked examples and boundaries: qSOFA, NEWS2, GCS, Centor, MELD-Na, Child-Pugh, CKD-EPI."""

from __future__ import annotations

from typing import Any

import pytest

from medagent.calculators import run_calculator
from medagent.calculators.hepatorenal import ckd_epi_2021_egfr


def points(result: dict[str, Any], criterion: str) -> float:
    return next(c["points"] for c in result["components"] if c["criterion"] == criterion)


@pytest.mark.parametrize(
    ("rr", "sbp", "altered", "score", "band"),
    [
        (21, 101, False, 0, "negative"),
        (22, 101, False, 1, "negative"),
        (22, 100, False, 2, "positive"),
        (30, 85, True, 3, "positive"),
    ],
)
def test_qsofa(rr: int, sbp: int, altered: bool, score: int, band: str) -> None:
    result = run_calculator(
        "qsofa", {"respiratory_rate": rr, "systolic_bp": sbp, "altered_mentation": altered}
    )
    assert (result["score"], result["interpretation"]["band"]) == (score, band)


NEWS2_NORMAL: dict[str, Any] = {
    "respiratory_rate": 16,
    "oxygen_saturation": 97,
    "supplemental_oxygen": False,
    "systolic_bp": 120,
    "heart_rate": 70,
    "consciousness": "alert",
    "temperature": {"value": 37.0, "unit": "°C"},
}


def news2(**changes: Any) -> dict[str, Any]:
    return run_calculator("news2", {**NEWS2_NORMAL, **changes})


def test_news2_worked_example_with_fahrenheit_is_high() -> None:
    result = news2(
        respiratory_rate=22,
        oxygen_saturation=95,
        systolic_bp=105,
        heart_rate=112,
        temperature={"value": 101.3, "unit": "°F"},
    )
    assert result["score"] == 7
    assert result["interpretation"]["band"] == "high"
    assert [c["points"] for c in result["components"]] == [2, 1, 0, 1, 2, 0, 1]
    assert result["inputs"]["temperature"]["value"] == 38.5
    assert result["inputs"]["spo2_scale"] == {"value": "scale_1", "defaulted": True}


def test_news2_single_red_score_is_low_medium() -> None:
    result = news2(consciousness="voice")
    assert result["score"] == 3
    assert result["interpretation"]["band"] == "low_medium"


@pytest.mark.parametrize(
    ("changes", "criterion", "expected"),
    [
        ({"respiratory_rate": 8}, "respiration", 3),
        ({"respiratory_rate": 9}, "respiration", 1),
        ({"respiratory_rate": 20}, "respiration", 0),
        ({"respiratory_rate": 21}, "respiration", 2),
        ({"respiratory_rate": 25}, "respiration", 3),
        ({"oxygen_saturation": 96}, "oxygen_sat", 0),
        ({"oxygen_saturation": 93}, "oxygen_sat", 2),
        ({"oxygen_saturation": 91}, "oxygen_sat", 3),
        ({"spo2_scale": "scale_2", "oxygen_saturation": 88}, "oxygen_sat", 0),
        ({"spo2_scale": "scale_2", "oxygen_saturation": 93}, "oxygen_sat", 0),
        (
            {"spo2_scale": "scale_2", "oxygen_saturation": 93, "supplemental_oxygen": True},
            "oxygen_sat",
            1,
        ),
        (
            {"spo2_scale": "scale_2", "oxygen_saturation": 97, "supplemental_oxygen": True},
            "oxygen_sat",
            3,
        ),
        ({"supplemental_oxygen": True}, "supplemental_o2", 2),
        ({"systolic_bp": 90}, "systolic_bp", 3),
        ({"systolic_bp": 111}, "systolic_bp", 0),
        ({"systolic_bp": 220}, "systolic_bp", 3),
        ({"heart_rate": 40}, "heart_rate", 3),
        ({"heart_rate": 91}, "heart_rate", 1),
        ({"heart_rate": 131}, "heart_rate", 3),
        ({"temperature": {"value": 35.0, "unit": "°C"}}, "temperature", 3),
        ({"temperature": {"value": 36.1, "unit": "°C"}}, "temperature", 0),
        # 100.4 °F is exactly 38.0 °C: float noise must not push it into the 38.1-39.0 band.
        ({"temperature": {"value": 100.4, "unit": "°F"}}, "temperature", 0),
        ({"temperature": {"value": 39.1, "unit": "degC"}}, "temperature", 2),
    ],
)
def test_news2_parameter_bands(changes: dict[str, Any], criterion: str, expected: int) -> None:
    assert points(news2(**changes), criterion) == expected


@pytest.mark.parametrize(
    ("eye", "verbal", "motor", "score", "band"),
    [
        (4, 5, 6, 15, "mild"),
        (3, 4, 6, 13, "mild"),
        (3, 3, 6, 12, "moderate"),
        (2, 2, 5, 9, "moderate"),
        (2, 2, 4, 8, "severe"),
        (1, 1, 1, 3, "severe"),
    ],
)
def test_gcs(eye: int, verbal: int, motor: int, score: int, band: str) -> None:
    result = run_calculator("gcs", {"eye": eye, "verbal": verbal, "motor": motor})
    assert (result["score"], result["interpretation"]["band"]) == (score, band)


CENTOR_BASE: dict[str, Any] = {
    "age": 30,
    "temperature": {"value": 37.0, "unit": "°C"},
    "cough_absent": False,
    "tender_anterior_cervical_nodes": False,
    "tonsillar_swelling_or_exudate": False,
}


@pytest.mark.parametrize(
    ("changes", "criterion", "expected"),
    [
        ({"age": 14}, "age_bonus", 1),
        ({"age": 15}, "age_bonus", 0),
        ({"age": 44}, "age_bonus", 0),
        ({"age": 45}, "age_bonus", -1),
        ({"temperature": {"value": 38.0, "unit": "°C"}}, "fever_history", 0),
        ({"temperature": {"value": 38.1, "unit": "°C"}}, "fever_history", 1),
        ({"temperature": {"value": 100.4, "unit": "°F"}}, "fever_history", 0),
        ({"temperature": {"value": 100.6, "unit": "F"}}, "fever_history", 1),
    ],
)
def test_centor_criteria(changes: dict[str, Any], criterion: str, expected: int) -> None:
    result = run_calculator("centor_mcisaac", {**CENTOR_BASE, **changes})
    assert points(result, criterion) == expected


@pytest.mark.parametrize(
    ("changes", "score", "band"),
    [
        ({"age": 50}, -1, "low"),
        (
            {
                "age": 50,
                "temperature": {"value": 38.5, "unit": "°C"},
                "cough_absent": True,
                "tender_anterior_cervical_nodes": True,
                "tonsillar_swelling_or_exudate": True,
            },
            3,
            "moderate",
        ),
        (
            {
                "age": 10,
                "temperature": {"value": 38.5, "unit": "°C"},
                "cough_absent": True,
                "tender_anterior_cervical_nodes": True,
                "tonsillar_swelling_or_exudate": True,
            },
            5,
            "high",
        ),
    ],
)
def test_centor_mcisaac_bands(changes: dict[str, Any], score: int, band: str) -> None:
    result = run_calculator("centor_mcisaac", {**CENTOR_BASE, **changes})
    assert (result["score"], result["interpretation"]["band"]) == (score, band)


def meld(**inputs: Any) -> dict[str, Any]:
    base = {
        "bilirubin": {"value": 1.0, "unit": "mg/dL"},
        "inr": 1.0,
        "creatinine": {"value": 1.0, "unit": "mg/dL"},
        "sodium": 137,
        "dialysis": False,
    }
    return run_calculator("meld_na", {**base, **inputs})


def test_meld_na_worked_example_in_si_units() -> None:
    # Bilirubin 42.75 µmol/L = 2.5 mg/dL, creatinine 168 µmol/L = 1.90 mg/dL, Na 129 mEq/L.
    result = meld(
        bilirubin={"value": 42.75, "unit": "µmol/L"},
        inr=1.8,
        creatinine={"value": 168, "unit": "umol/L"},
        sodium={"value": 129, "unit": "mEq/L"},
    )
    assert result["score"] == 27
    assert result["details"] == {"meld_i": 23, "sodium_term_applied": True}
    assert result["interpretation"]["band"] == "meld_20_29"
    assert all(c["points"] is None for c in result["components"])


@pytest.mark.parametrize(
    ("inputs", "score", "band"),
    [
        ({}, 6, "meld_lt_10"),
        ({"creatinine": {"value": 1.6, "unit": "mg/dL"}, "sodium": 125}, 11, "meld_10_19"),
        ({"creatinine": {"value": 1.7, "unit": "mg/dL"}, "sodium": 125}, 23, "meld_20_29"),
        ({"dialysis": True}, 20, "meld_20_29"),
        (
            {
                "bilirubin": {"value": 10, "unit": "mg/dL"},
                "inr": 2.5,
                "creatinine": {"value": 2.5, "unit": "mg/dL"},
            },
            34,
            "meld_30_39",
        ),
        (
            {"bilirubin": {"value": 30, "unit": "mg/dL"}, "inr": 5, "dialysis": True},
            40,
            "meld_ge_40",
        ),
    ],
)
def test_meld_na_bands(inputs: dict[str, Any], score: int, band: str) -> None:
    result = meld(**inputs)
    assert (result["score"], result["interpretation"]["band"]) == (score, band)


CHILD_BASE: dict[str, Any] = {
    "bilirubin": {"value": 1.0, "unit": "mg/dL"},
    "albumin": {"value": 4.0, "unit": "g/dL"},
    "inr": 1.0,
    "ascites": "none",
    "encephalopathy": "none",
}


@pytest.mark.parametrize(
    ("changes", "criterion", "expected"),
    [
        ({"bilirubin": {"value": 1.9, "unit": "mg/dL"}}, "bilirubin", 1),
        ({"bilirubin": {"value": 2.0, "unit": "mg/dL"}}, "bilirubin", 2),
        ({"bilirubin": {"value": 34.2, "unit": "µmol/L"}}, "bilirubin", 2),
        ({"bilirubin": {"value": 3.0, "unit": "mg/dL"}}, "bilirubin", 2),
        ({"bilirubin": {"value": 3.1, "unit": "mg/dL"}}, "bilirubin", 3),
        ({"albumin": {"value": 3.6, "unit": "g/dL"}}, "albumin", 1),
        ({"albumin": {"value": 35, "unit": "g/L"}}, "albumin", 2),
        ({"albumin": {"value": 2.8, "unit": "g/dL"}}, "albumin", 2),
        ({"albumin": {"value": 2.7, "unit": "g/dL"}}, "albumin", 3),
        ({"inr": 1.69}, "inr", 1),
        ({"inr": 1.7}, "inr", 2),
        ({"inr": 2.3}, "inr", 2),
        ({"inr": 2.31}, "inr", 3),
    ],
)
def test_child_pugh_thresholds(changes: dict[str, Any], criterion: str, expected: int) -> None:
    assert points(run_calculator("child_pugh", {**CHILD_BASE, **changes}), criterion) == expected


@pytest.mark.parametrize(
    ("changes", "score", "band"),
    [
        ({"ascites": "slight"}, 6, "class_a"),
        ({"ascites": "slight", "encephalopathy": "grade_1_2"}, 7, "class_b"),
        (
            {"ascites": "moderate_to_severe", "encephalopathy": "grade_1_2", "inr": 1.8},
            9,
            "class_b",
        ),
        (
            {"ascites": "moderate_to_severe", "encephalopathy": "grade_3_4", "inr": 1.8},
            10,
            "class_c",
        ),
    ],
)
def test_child_pugh_classes(changes: dict[str, Any], score: int, band: str) -> None:
    result = run_calculator("child_pugh", {**CHILD_BASE, **changes})
    assert (result["score"], result["interpretation"]["band"]) == (score, band)


@pytest.mark.parametrize(
    ("creatinine", "age", "sex", "egfr", "band"),
    [
        ({"value": 1.0, "unit": "mg/dL"}, 50, "female", 69, "g2"),
        ({"value": 88.4, "unit": "µmol/L"}, 50, "male", 92, "g1"),
        # Male with Scr <= 0.9 uses kappa 0.9 and alpha -0.302 (Inker 2021); MedCalc-Bench's
        # reference implementation uses kappa 0.7 here and would report 94.
        ({"value": 0.8, "unit": "mg/dL"}, 60, "male", 101, "g1"),
        ({"value": 3.0, "unit": "mg/dL"}, 70, "male", 22, "g4"),
        ({"value": 6.0, "unit": "mg/dL"}, 70, "male", 9, "g5"),
    ],
)
def test_ckd_epi_2021(creatinine: dict[str, Any], age: int, sex: str, egfr: int, band: str) -> None:
    result = run_calculator("ckd_epi_2021", {"creatinine": creatinine, "age": age, "sex": sex})
    assert (result["details"]["egfr_rounded"], result["interpretation"]["band"]) == (egfr, band)
    assert round(result["score"]) == egfr
    assert result["score_unit"] == "mL/min/1.73 m2"


def test_ckd_epi_2021_matches_the_published_equation() -> None:
    # 142 x (1.2/0.7)^-1.200 x 0.9938^65 x 1.012 for a 65-year-old woman.
    expected = 142 * (1.2 / 0.7) ** -1.2 * 0.9938**65 * 1.012
    assert ckd_epi_2021_egfr(1.2, 65, female=True) == pytest.approx(expected)
    assert round(expected) == 50


def test_ckd_epi_2021_bands_and_reports_the_unrounded_egfr() -> None:
    # 59.88 mL/min/1.73 m2 is below 60, so KDIGO G3a; rounding first would report G2.
    result = run_calculator(
        "ckd_epi_2021",
        {"creatinine": {"value": 1.18, "unit": "mg/dL"}, "age": 40, "sex": "female"},
    )
    assert result["score"] == pytest.approx(ckd_epi_2021_egfr(1.18, 40, female=True))
    assert 59.5 < result["score"] < 60
    assert result["interpretation"]["band"] == "g3a"
    assert result["details"]["egfr_rounded"] == 60
