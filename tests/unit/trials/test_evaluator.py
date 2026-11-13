"""Criterion-level behaviour of the trial pre-screen: operators, units, missing data, ages."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from medagent.trials.schema import INSUFFICIENT_DATA, MET, NOT_MET, REQUIRES_HUMAN_REVIEW
from tests.unit.trials.builders import (
    ICD10CM,
    LOINC,
    PATIENT,
    SNOMED,
    bundle,
    coded_status,
    condition,
    lab,
    medication,
    observation,
    result_of,
    screen,
    status_of,
    trial,
)

# ---------------------------------------------------------------------------
# Lab thresholds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("operator", "threshold", "value", "expected"),
    [
        (">=", 30, 30, MET),
        (">=", 30, 29.99, NOT_MET),
        (">", 30, 30, NOT_MET),
        (">", 30, 30.01, MET),
        ("<=", 30, 30, MET),
        ("<=", 30, 30.01, NOT_MET),
        ("<", 30, 30, NOT_MET),
        ("<", 30, 29.99, MET),
    ],
)
def test_each_operator_is_exact_at_the_boundary(
    operator: str, threshold: float, value: float, expected: str
) -> None:
    screening = screen(bundle(observation(value)), trial(lab(operator=operator, value=threshold)))

    assert status_of(screening, "lab") == expected


@pytest.mark.parametrize(
    ("value", "expected"), [(7.0, MET), (10.5, MET), (6.99, NOT_MET), (10.51, NOT_MET)]
)
def test_between_is_inclusive_at_both_ends(value: float, expected: str) -> None:
    criterion = lab(operator="between", value=None, unit="%", low=7.0, high=10.5)
    hba1c = observation(value, "%", code={"system": LOINC, "code": "4548-4"}, text="HbA1c")
    criterion["codes"] = [{"system": LOINC, "code": "4548-4"}]

    assert status_of(screen(bundle(hba1c), trial(criterion)), "lab") == expected


@pytest.mark.parametrize(
    ("comparator", "value", "operator", "threshold", "expected"),
    [
        (">", 60, ">=", 30, MET),  # eGFR reported as ">60"
        ("<", 5, ">=", 30, NOT_MET),
        ("<", 5, "<=", 3, INSUFFICIENT_DATA),  # censored: could be 2 or 4
        (">=", 30, ">=", 30, MET),
        (">", 30, ">", 30, MET),
        ("<=", 30, "<", 30, INSUFFICIENT_DATA),
    ],
)
def test_censored_values_decide_only_when_every_possible_value_agrees(
    comparator: str, value: float, operator: str, threshold: float, expected: str
) -> None:
    screening = screen(
        bundle(observation(value, comparator=comparator)),
        trial(lab(operator=operator, value=threshold)),
    )

    assert status_of(screening, "lab") == expected


def test_units_are_converted_exactly_within_one_dimension() -> None:
    # 0.5 mL/s/1.73m2 is exactly 30 mL/min/1.73m2: the boundary must still be met.
    egfr = observation(0.5, "mL/s/1.73m2", ucum="mL/s/{1.73_m2}")
    hemoglobin = observation(90, "g/L", code={"system": LOINC, "code": "718-7"}, text="Hb")
    neutrophils = observation(1500, "cells/uL", code={"system": LOINC, "code": "751-8"}, text="ANC")
    screening = screen(
        bundle(egfr, hemoglobin, neutrophils),
        trial(
            lab("egfr"),
            lab("hb", value=9, unit="g/dL", codes=({"system": LOINC, "code": "718-7"},)),
            lab("anc", value=1.5, unit="10*9/L", codes=({"system": LOINC, "code": "751-8"},)),
        ),
    )

    assert status_of(screening, "egfr") == MET
    assert status_of(screening, "hb") == MET
    assert status_of(screening, "anc") == MET
    rationale = result_of(screening, "egfr")["rationale"]
    assert "0.5 mL/s/1.73m2 (= 30 mL/min/1.73m2) satisfies >= 30 mL/min/1.73m2" in rationale


@pytest.mark.parametrize(
    ("value", "unit", "criterion_unit"),
    [
        (1.1, "mg/dL", "umol/L"),  # mass vs substance concentration needs a molar mass
        (52, None, "mL/min/1.73m2"),  # no unit recorded
        (52, "furlongs/fortnight", "mL/min/1.73m2"),  # unknown unit
    ],
)
def test_incompatible_or_missing_units_are_insufficient_data(
    value: float, unit: str | None, criterion_unit: str
) -> None:
    screening = screen(bundle(observation(value, unit)), trial(lab(unit=criterion_unit)))

    result = result_of(screening, "lab")
    assert result["status"] == INSUFFICIENT_DATA
    assert "1 missing or incompatible unit" in result["rationale"]


def test_a_dimensionless_criterion_accepts_a_unitless_value() -> None:
    inr = observation(2.1, None, code={"system": LOINC, "code": "6301-6"}, text="INR")
    criterion = lab(
        operator="<=", value=1.5, unit="{INR}", codes=({"system": LOINC, "code": "6301-6"},)
    )

    assert status_of(screen(bundle(inr), trial(criterion)), "lab") == NOT_MET


@pytest.mark.parametrize(("alt", "expected"), [(120, MET), (121, NOT_MET)])
def test_uln_thresholds_use_the_reference_range_upper_limit(alt: int, expected: str) -> None:
    observed = observation(alt, "U/L", code={"system": LOINC, "code": "1742-6"}, high=40)
    criterion = lab(
        operator="<=",
        value=3,
        unit=None,
        relative_to="uln",
        codes=({"system": LOINC, "code": "1742-6"},),
    )

    assert status_of(screen(bundle(observed), trial(criterion)), "lab") == expected


def test_uln_threshold_without_a_reference_range_is_insufficient() -> None:
    observed = observation(28, "U/L", code={"system": LOINC, "code": "1742-6"})
    criterion = lab(
        operator="<=",
        value=3,
        unit=None,
        relative_to="uln",
        codes=({"system": LOINC, "code": "1742-6"},),
    )

    result = result_of(screen(bundle(observed), trial(criterion)), "lab")
    assert result["status"] == INSUFFICIENT_DATA
    assert "no usable reference-range upper limit" in result["rationale"]


@pytest.mark.parametrize(
    ("observations", "fragment"),
    [
        ((), "No matching Observation among 0 supplied"),
        ((observation(52, effective="2026-09-01"),), "1 older than 28 days"),
        ((observation(52, effective=None),), "1 undated"),
        ((observation(52, effective="2026-11-20"),), "1 dated after as_of"),
        ((observation("high", unit=None),), "1 no numeric value"),
    ],
)
def test_missing_stale_or_unusable_labs_are_insufficient_data(
    observations: tuple[dict[str, Any], ...], fragment: str
) -> None:
    screening = screen(bundle(*observations), trial(lab(within_days=28)))

    result = result_of(screening, "lab")
    assert result["status"] == INSUFFICIENT_DATA
    assert fragment in result["rationale"]


def test_the_most_recent_lab_in_the_window_decides() -> None:
    older = observation(80, effective="2026-10-01")
    newer = observation(25, effective="2026-11-01")
    screening = screen(bundle(older, newer), trial(lab(within_days=90)))

    result = result_of(screening, "lab")
    assert result["status"] == NOT_MET
    assert [item["date"] for item in result["evidence"]] == ["2026-11-01"]


def test_conflicting_same_day_labs_need_review_data() -> None:
    screening = screen(
        bundle(observation(25, effective="2026-11-01"), observation(45, effective="2026-11-01")),
        trial(lab()),
    )

    result = result_of(screening, "lab")
    assert result["status"] == INSUFFICIENT_DATA
    assert "disagree" in result["rationale"]


def test_invalidated_observations_are_never_used() -> None:
    screening = screen(bundle(observation(10, status="entered-in-error")), trial(lab()))

    assert status_of(screening, "lab") == INSUFFICIENT_DATA
    assert any("invalidated" in note for note in screening.structured()["data_notes"])


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------


def _condition_criterion(**extra: Any) -> dict[str, Any]:
    criterion = {"id": "cond", "type": "condition", "text": "diabetes"}
    criterion.update(extra)
    criterion.setdefault("codes", [{"system": SNOMED, "code": "44054006"}])
    return criterion


@pytest.mark.parametrize(
    ("resource", "criterion", "expected"),
    [
        (condition(), _condition_criterion(), MET),
        (
            condition((ICD10CM, "E11.9")),
            _condition_criterion(codes=[{"system": ICD10CM, "code": "E11", "match": "prefix"}]),
            MET,
        ),
        (
            condition((ICD10CM, "E11.9")),
            _condition_criterion(codes=[{"system": ICD10CM, "code": "E11"}]),
            NOT_MET,
        ),
        (
            condition((SNOMED, "1")),
            {"id": "cond", "type": "condition", "text": "t", "terms": ["type 2 diabetes"]},
            MET,
        ),
        (
            condition((SNOMED, "1")),
            {"id": "cond", "type": "condition", "text": "t", "terms": ["diabetes type 2"]},
            NOT_MET,
        ),
        (condition(status="resolved"), _condition_criterion(status="active"), NOT_MET),
        (condition(status="resolved"), _condition_criterion(), MET),
        (condition(status=None), _condition_criterion(status="active"), INSUFFICIENT_DATA),
        (condition(verification="provisional"), _condition_criterion(), INSUFFICIENT_DATA),
        (condition(onset="2026-08-01"), _condition_criterion(within_days=180), MET),
        (condition(onset="2025-01-01"), _condition_criterion(within_days=180), NOT_MET),
        (condition(), _condition_criterion(within_days=180), INSUFFICIENT_DATA),
        (condition(), _condition_criterion(presence="absent"), NOT_MET),
        (condition((SNOMED, "38341003")), _condition_criterion(presence="absent"), MET),
    ],
)
def test_condition_matching_status_window_and_presence(
    resource: dict[str, Any], criterion: dict[str, Any], expected: str
) -> None:
    assert status_of(screen(bundle(resource), trial(criterion)), "cond") == expected


def test_conditions_absent_from_a_record_without_conditions_are_insufficient() -> None:
    screening = screen(
        bundle(), trial(_condition_criterion(), _condition_criterion(id="no", presence="absent"))
    )

    assert status_of(screening, "cond") == INSUFFICIENT_DATA
    assert status_of(screening, "no") == INSUFFICIENT_DATA
    assert result_of(screening, "cond")["rationale"] == "No Condition resources were supplied."


def test_absence_is_explained_as_a_partial_record() -> None:
    result = result_of(
        screen(bundle(condition((SNOMED, "1"))), trial(_condition_criterion())), "cond"
    )

    assert result["status"] == NOT_MET
    assert "among 1 supplied Condition resource(s)" in result["rationale"]
    assert "not proof of absence" in result["rationale"]


# ---------------------------------------------------------------------------
# Medications
# ---------------------------------------------------------------------------


def _medication_criterion(**extra: Any) -> dict[str, Any]:
    return {"id": "med", "type": "medication", "text": "anticoagulant", **extra}


@pytest.mark.parametrize(
    ("resources", "criterion", "expected"),
    [
        (
            (medication("Warfarin sodium 5 mg tablet"),),
            _medication_criterion(ingredients=["warfarin"]),
            MET,
        ),
        (
            (medication("Atorvastatin 40 mg tablet"),),
            _medication_criterion(ingredients=["statin"]),
            NOT_MET,
        ),
        (
            (medication("Apixaban 5 mg tablet"),),
            _medication_criterion(classes=["anticoagulants"]),
            MET,
        ),
        (
            (medication("Brand X", rxnorm="1364445"),),
            _medication_criterion(rxnorm_codes=["1364445"]),
            MET,
        ),
        (
            (medication("Warfarin 5 mg", status="stopped"),),
            _medication_criterion(ingredients=["warfarin"]),
            NOT_MET,
        ),
        (
            (medication("Warfarin 5 mg", status="draft"),),
            _medication_criterion(ingredients=["warfarin"]),
            NOT_MET,
        ),
        (
            (medication(None, rxnorm="855332"),),
            _medication_criterion(ingredients=["warfarin"]),
            INSUFFICIENT_DATA,
        ),
        ((), _medication_criterion(ingredients=["warfarin"]), INSUFFICIENT_DATA),
        (
            (medication("Metformin 500 mg", resource_type="MedicationStatement"),),
            _medication_criterion(ingredients=["warfarin"], presence="absent"),
            MET,
        ),
    ],
)
def test_medication_matching_reuses_whole_token_normalisation(
    resources: tuple[dict[str, Any], ...], criterion: dict[str, Any], expected: str
) -> None:
    assert status_of(screen(bundle(*resources), trial(criterion)), "med") == expected


def test_medication_evidence_points_at_the_resource_without_identifiers() -> None:
    screening = screen(
        bundle(
            medication("Warfarin 5 mg tablet", rxnorm="855332", resource_type="MedicationStatement")
        ),
        trial(_medication_criterion(ingredients=["warfarin"])),
    )

    [evidence] = result_of(screening, "med")["evidence"]
    assert evidence["resource_type"] == "MedicationStatement"
    assert evidence["code"] == "855332"
    assert evidence["display"] == "Warfarin 5 mg tablet"


# ---------------------------------------------------------------------------
# Pregnancy and lactation
# ---------------------------------------------------------------------------

NOT_PREGNANT = (SNOMED, "60001007")
PREGNANT = (SNOMED, "77386006")


@pytest.mark.parametrize(
    ("resources", "context", "within_days", "expected"),
    [
        ((coded_status("82810-3", NOT_PREGNANT, "2026-11-02"),), None, 30, NOT_MET),
        ((coded_status("82810-3", PREGNANT, "2026-11-02"),), None, 30, MET),
        ((coded_status("82810-3", NOT_PREGNANT, "2026-06-02"),), None, 30, INSUFFICIENT_DATA),
        (
            (coded_status("82810-3", (SNOMED, "261665006"), "2026-11-02"),),
            None,
            None,
            INSUFFICIENT_DATA,
        ),
        (
            (coded_status("82810-3", ("http://example.org", "x"), "2026-11-02"),),
            None,
            None,
            INSUFFICIENT_DATA,
        ),
        ((), None, None, INSUFFICIENT_DATA),
        ((), {"pregnant": False}, 30, NOT_MET),
        ((coded_status("82810-3", PREGNANT, "2026-11-02"),), {"pregnant": False}, 30, NOT_MET),
        (
            (
                coded_status("82810-3", PREGNANT, "2026-11-02"),
                coded_status("82810-3", NOT_PREGNANT, "2026-11-02"),
            ),
            None,
            None,
            INSUFFICIENT_DATA,
        ),
    ],
)
def test_pregnancy_comes_from_coded_status_or_the_caller_never_from_sex(
    resources: tuple[dict[str, Any], ...],
    context: dict[str, bool] | None,
    within_days: int | None,
    expected: str,
) -> None:
    criterion: dict[str, Any] = {"id": "preg", "type": "pregnancy", "text": "Pregnant"}
    if within_days is not None:
        criterion["within_days"] = within_days

    screening = screen(bundle(*resources), trial(exclusion=(criterion,)), patient_context=context)

    assert status_of(screening, "preg") == expected


def test_lactation_uses_the_breastfeeding_status_answer_list() -> None:
    feeding = coded_status("63895-7", (LOINC, "LA29252-6"), "2026-11-01")
    criterion = {"id": "lact", "type": "lactation", "text": "Breastfeeding"}

    screening = screen(bundle(feeding), trial(exclusion=(criterion,)))

    assert status_of(screening, "lact") == MET
    assert screening.structured()["trials"][0]["status"] == "likely_ineligible"


# ---------------------------------------------------------------------------
# Age and sex (ClinicalTrials.gov eligibilityModule)
# ---------------------------------------------------------------------------


def _patient(**fields: Any) -> dict[str, Any]:
    patient = {key: value for key, value in PATIENT.items() if key not in fields}
    patient.update({key: value for key, value in fields.items() if value is not None})
    return patient


@pytest.mark.parametrize(
    ("birth_date", "module", "criterion_id", "as_of", "expected"),
    [
        ("2008-11-12", {"minimumAge": "18 Years"}, "eligibility.minimum_age", "2026-11-12", MET),
        (
            "2008-11-13",
            {"minimumAge": "18 Years"},
            "eligibility.minimum_age",
            "2026-11-12",
            NOT_MET,
        ),
        ("1960-11-13", {"maximumAge": "65 Years"}, "eligibility.maximum_age", "2026-11-12", MET),
        (
            "1960-11-12",
            {"maximumAge": "65 Years"},
            "eligibility.maximum_age",
            "2026-11-12",
            NOT_MET,
        ),
        ("2026-05-12", {"minimumAge": "6 Months"}, "eligibility.minimum_age", "2026-11-12", MET),
        (
            "2026-05-13",
            {"minimumAge": "6 Months"},
            "eligibility.minimum_age",
            "2026-11-12",
            NOT_MET,
        ),
        ("2026-10-15", {"maximumAge": "28 Days"}, "eligibility.maximum_age", "2026-11-12", MET),
        ("2026-10-14", {"maximumAge": "28 Days"}, "eligibility.maximum_age", "2026-11-12", NOT_MET),
        ("2008-02-29", {"minimumAge": "18 Years"}, "eligibility.minimum_age", "2026-02-28", MET),
        (
            "2008-02-29",
            {"minimumAge": "18 Years"},
            "eligibility.minimum_age",
            "2026-02-27",
            NOT_MET,
        ),
        ("1961", {"maximumAge": "65 Years"}, "eligibility.maximum_age", "2026-11-12", MET),
        (
            "1961",
            {"maximumAge": "64 Years"},
            "eligibility.maximum_age",
            "2026-11-12",
            INSUFFICIENT_DATA,
        ),
        (
            "1961-05",
            {"maximumAge": "64 Years"},
            "eligibility.maximum_age",
            "2026-05-20",
            INSUFFICIENT_DATA,
        ),
        ("1961-05", {"maximumAge": "64 Years"}, "eligibility.maximum_age", "2026-06-01", NOT_MET),
        (
            None,
            {"minimumAge": "18 Years"},
            "eligibility.minimum_age",
            "2026-11-12",
            INSUFFICIENT_DATA,
        ),
        (
            "1990-01-01",
            {"minimumAge": "24 Hours"},
            "eligibility.minimum_age",
            "2026-11-12",
            REQUIRES_HUMAN_REVIEW,
        ),
    ],
)
def test_age_limits_are_inclusive_clinicaltrials_gov_normalized_times(
    birth_date: str | None, module: dict[str, Any], criterion_id: str, as_of: str, expected: str
) -> None:
    screening = screen(
        bundle(patient=_patient(birthDate=birth_date)),
        trial(module=module),
        as_of=date.fromisoformat(as_of),
    )

    assert status_of(screening, criterion_id) == expected


def test_no_limit_means_no_age_criterion() -> None:
    screening = screen(bundle(), trial(lab(), module={"minimumAge": "N/A", "sex": "ALL"}))

    ids = [item["criterion_id"] for item in screening.structured()["trials"][0]["criteria"]]
    assert ids == ["lab"]


@pytest.mark.parametrize(
    ("gender", "module", "expected"),
    [
        ("female", {"sex": "FEMALE"}, MET),
        ("female", {"sex": "MALE"}, NOT_MET),
        ("other", {"sex": "FEMALE"}, INSUFFICIENT_DATA),
        ("unknown", {"sex": "MALE"}, INSUFFICIENT_DATA),
        (None, {"sex": "FEMALE"}, INSUFFICIENT_DATA),
        ("female", {"sex": "FEMALE", "genderBased": True}, REQUIRES_HUMAN_REVIEW),
    ],
)
def test_sex_uses_administrative_gender_and_defers_gender_based_trials(
    gender: str | None, module: dict[str, Any], expected: str
) -> None:
    patient = (
        _patient(gender=gender) if gender else {k: v for k, v in PATIENT.items() if k != "gender"}
    )

    screening = screen(bundle(patient=patient), trial(module=module))

    assert status_of(screening, "eligibility.sex") == expected


# ---------------------------------------------------------------------------
# Free text
# ---------------------------------------------------------------------------


def test_free_text_criteria_always_require_human_review() -> None:
    criterion = {"id": "ecog", "type": "free_text", "text": "ECOG performance status 0-1"}

    screening = screen(bundle(), trial(criterion))

    result = result_of(screening, "ecog")
    assert result["status"] == REQUIRES_HUMAN_REVIEW
    assert result["evidence"] == []
    assert screening.structured()["trials"][0]["status"] == "needs_review"
