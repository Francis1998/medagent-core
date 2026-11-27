"""Input validation, unit handling and registry metadata of the calculator registry."""

from __future__ import annotations

import math
from typing import Any
from unittest.mock import MagicMock

import pytest

from medagent.calculators import (
    CALCULATORS,
    CalculatorInputError,
    UnknownCalculatorError,
    catalogue,
    describe_calculator,
    registry,
    run_calculator,
)
from medagent.calculators.schema import RUN_OUTPUT_SCHEMA
from medagent.mcp.schema import validate
from medagent.safety.disclaimer import MANDATORY_DISCLAIMER

CKD = {"creatinine": {"value": 1.0, "unit": "mg/dL"}, "age": 50, "sex": "male"}


def problems(calculator_id: str, inputs: Any) -> list[str]:
    with pytest.raises(CalculatorInputError) as excinfo:
        run_calculator(calculator_id, inputs)
    return excinfo.value.problems


def test_missing_required_inputs_are_errors_never_assumed_absent() -> None:
    found = problems("qsofa", {"respiratory_rate": 24})
    assert found == ["inputs.systolic_bp is required", "inputs.altered_mentation is required"]


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        (
            {**CKD, "creatinine": 1.0},
            'inputs.creatinine needs an explicit unit: {"value": <number>',
        ),
        (
            {**CKD, "creatinine": {"value": 1.0, "unit": "mmol/L"}},
            "inputs.creatinine.unit must be one of mg/dL, µmol/L",
        ),
        (
            {**CKD, "creatinine": {"value": "1.0", "unit": "mg/dL"}},
            "inputs.creatinine.value must be a finite number",
        ),
        (
            {**CKD, "creatinine": {"value": math.nan, "unit": "mg/dL"}},
            "inputs.creatinine.value must be a finite number",
        ),
        ({**CKD, "creatinine": {"value": 1.0}}, "inputs.creatinine must be a number"),
        (
            {**CKD, "creatinine": {"value": 30, "unit": "mg/dL"}},
            "inputs.creatinine must be between 0.1 and 25 mg/dL",
        ),
        (
            {**CKD, "creatinine": {"value": 2500, "unit": "µmol/L"}},
            "inputs.creatinine must be between 0.1 and 25 mg/dL",
        ),
        ({**CKD, "age": 17}, "inputs.age must be between 18 and 120 years"),
        ({**CKD, "age": 50.5}, "inputs.age must be a whole number"),
        ({**CKD, "age": True}, "inputs.age must be a finite number"),
        ({**CKD, "sex": "unknown"}, "inputs.sex must be one of female, male"),
        (
            {**CKD, "Patient Name": "Jane Canary"},
            "inputs has unexpected properties (allowed: age, creatinine, sex)",
        ),
    ],
)
def test_invalid_inputs_name_the_input_without_echoing_the_value(
    inputs: dict[str, Any], message: str
) -> None:
    found = problems("ckd_epi_2021", inputs)
    assert any(problem.startswith(message) for problem in found), found
    joined = " ".join(found)
    for leaked in ("Jane", "Canary", "Patient Name", "2500", "50.5", "unknown"):
        assert leaked not in joined


def test_booleans_must_be_json_booleans() -> None:
    found = problems("qsofa", {"respiratory_rate": 24, "systolic_bp": 95, "altered_mentation": 1})
    assert found == ["inputs.altered_mentation must be true or false"]


def test_inputs_must_be_an_object() -> None:
    assert problems("gcs", [4, 5, 6]) == ["inputs must be an object"]


def test_unknown_calculator_is_reported_without_echoing_the_id() -> None:
    with pytest.raises(UnknownCalculatorError) as excinfo:
        run_calculator("Jane Canary score", {})
    assert "Jane" not in str(excinfo.value)


def test_unit_spellings_are_normalised() -> None:
    for unit in ("umol/L", "µmol/L", "μmol/L", "UMOL/L"):
        result = run_calculator(
            "ckd_epi_2021", {**CKD, "creatinine": {"value": 88.4, "unit": unit}}
        )
        assert result["inputs"]["creatinine"]["value"] == 1.0


def test_logs_carry_the_calculator_id_and_band_only(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MagicMock()
    monkeypatch.setattr(registry, "logger", fake)
    run_calculator("ckd_epi_2021", CKD)
    with pytest.raises(CalculatorInputError):
        run_calculator("ckd_epi_2021", {**CKD, "age": 7})
    fake.info.assert_called_once_with("calculator_run", calculator="ckd_epi_2021", band="g1")
    fake.warning.assert_called_once_with(
        "calculator_rejected", calculator="ckd_epi_2021", problems=1
    )


def test_registry_metadata_is_complete_and_sorted() -> None:
    ids = [calculator.id for calculator in CALCULATORS]
    assert ids == sorted(ids)
    assert len(ids) == 13
    for calculator in CALCULATORS:
        assert calculator.citations and calculator.limitations and calculator.bands
        assert all(c.doi or c.pmid or c.url for c in calculator.citations)
        assert len({band.id for band in calculator.bands}) == len(calculator.bands)
        spec = describe_calculator(calculator.id)
        assert spec["disclaimer"] == MANDATORY_DISCLAIMER
        assert spec["input_schema"]["required"] == [
            i["name"] for i in spec["inputs"] if i["required"]
        ]


def test_catalogue_filters_by_category_and_id() -> None:
    assert catalogue()["count"] == 13
    hepatology = catalogue("hepatology")
    assert [c["id"] for c in hepatology["calculators"]] == ["child_pugh", "meld_na"]
    assert catalogue(calculator_id="gcs")["count"] == 1
    with pytest.raises(UnknownCalculatorError):
        catalogue(calculator_id="nope")


EXAMPLES: dict[str, dict[str, Any]] = {
    "centor_mcisaac": {
        "age": 30,
        "temperature": {"value": 38.4, "unit": "°C"},
        "cough_absent": True,
        "tender_anterior_cervical_nodes": False,
        "tonsillar_swelling_or_exudate": True,
    },
    "cha2ds2_vasc": {
        "age": 72,
        "sex": "female",
        "congestive_heart_failure": False,
        "hypertension": True,
        "diabetes": True,
        "stroke_tia_thromboembolism": False,
        "vascular_disease": False,
    },
    "child_pugh": {
        "bilirubin": {"value": 2.5, "unit": "mg/dL"},
        "albumin": {"value": 30, "unit": "g/L"},
        "inr": 1.8,
        "ascites": "slight",
        "encephalopathy": "none",
    },
    "ckd_epi_2021": CKD,
    "curb_65": {
        "confusion": False,
        "urea": {"value": 8.2, "unit": "mmol/L"},
        "respiratory_rate": 24,
        "systolic_bp": 118,
        "diastolic_bp": 70,
        "age": 71,
    },
    "gcs": {"eye": 3, "verbal": 4, "motor": 6},
    "has_bled": {
        "age": 70,
        "uncontrolled_hypertension": False,
        "abnormal_renal_function": False,
        "abnormal_liver_function": False,
        "stroke_history": False,
        "bleeding_history": True,
        "labile_inr": False,
        "antiplatelet_or_nsaid": True,
        "alcohol_excess": False,
    },
    "heart": {
        "history": "moderately_suspicious",
        "ecg": "normal",
        "age": 58,
        "hypercholesterolemia": True,
        "hypertension": True,
        "diabetes": False,
        "smoking": False,
        "family_history": False,
        "obesity": False,
        "atherosclerotic_disease": False,
        "troponin": 20,
        "troponin_uln": 14,
    },
    "meld_na": {
        "bilirubin": {"value": 2.5, "unit": "mg/dL"},
        "inr": 1.8,
        "creatinine": {"value": 1.9, "unit": "mg/dL"},
        "sodium": 129,
        "dialysis": False,
    },
    "news2": {
        "respiratory_rate": 22,
        "oxygen_saturation": 95,
        "supplemental_oxygen": False,
        "systolic_bp": 105,
        "heart_rate": 112,
        "consciousness": "alert",
        "temperature": {"value": 38.5, "unit": "°C"},
    },
    "perc": {
        "age": 35,
        "heart_rate": 88,
        "oxygen_saturation": 98,
        "unilateral_leg_swelling": False,
        "hemoptysis": False,
        "recent_surgery_or_trauma": False,
        "prior_pe_or_dvt": False,
        "hormone_use": False,
    },
    "qsofa": {"respiratory_rate": 24, "systolic_bp": 95, "altered_mentation": False},
    "wells_pe": {
        "clinical_dvt_signs": True,
        "pe_most_likely_diagnosis": True,
        "heart_rate": 90,
        "immobilization_or_recent_surgery": False,
        "previous_dvt_or_pe": False,
        "hemoptysis": False,
        "malignancy": False,
    },
}


@pytest.mark.parametrize("calculator_id", sorted(EXAMPLES))
def test_every_result_matches_the_output_schema(calculator_id: str) -> None:
    result = run_calculator(calculator_id, EXAMPLES[calculator_id])
    assert validate(result, RUN_OUTPUT_SCHEMA, "result") == []
    assert result["disclaimer"] == MANDATORY_DISCLAIMER
    assert result["calculator"]["id"] == calculator_id
    assert result["interpretation"]["band"] in {
        b["band"] for b in describe_calculator(calculator_id)["bands"]
    }


def test_examples_cover_every_calculator() -> None:
    assert sorted(EXAMPLES) == sorted(c.id for c in CALCULATORS)
