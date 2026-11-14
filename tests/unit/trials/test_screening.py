"""Trial status, ranking, privacy and validation of the research-only trial pre-screen."""

from __future__ import annotations

import json
import random
import subprocess
import sys
from typing import Any

import pytest

from medagent.mcp.schema import validate
from medagent.safety.disclaimer import MANDATORY_DISCLAIMER
from medagent.safety.pii_hasher import hash_pii
from medagent.trials.criteria import TrialInputError
from medagent.trials.schema import SCREEN_OUTPUT_SCHEMA
from medagent.trials.screening import canonical_json, screen_trials_request
from tests.unit.trials.builders import (
    AS_OF,
    IDENTIFIERS,
    PATIENT,
    ROOT,
    SNOMED,
    bundle,
    condition,
    example,
    lab,
    medication,
    observation,
    result_of,
    screen,
    trial,
    trial_of,
)

ONC = "EXAMPLE-ONC-001"


def _example_screening(**kwargs: Any) -> Any:
    return screen(example("patient-bundle.json"), *example("example-trials.json"), **kwargs)


# ---------------------------------------------------------------------------
# Trial status and exclusion precedence
# ---------------------------------------------------------------------------


def test_an_exclusion_that_is_met_wins_even_when_inclusions_are_undecided() -> None:
    anticoagulant = {
        "id": "exc-oac",
        "type": "medication",
        "text": "OAC",
        "ingredients": ["warfarin"],
    }
    unknown_inclusion = {"id": "inc-ecog", "type": "free_text", "text": "ECOG 0-1"}
    screening = screen(
        bundle(medication("Warfarin 5 mg tablet")),
        trial(unknown_inclusion, lab("inc-egfr"), exclusion=(anticoagulant,)),
    )

    result = trial_of(screening)
    assert result["status"] == "likely_ineligible"
    assert result["blocking_criteria"] == ["exc-oac"]
    assert set(result["open_criteria"]) == {"inc-ecog", "inc-egfr"}


def test_blocking_criteria_list_exclusions_before_inclusions() -> None:
    no_diabetes = {
        "id": "inc-dm",
        "type": "condition",
        "text": "Diabetes",
        "codes": [{"system": SNOMED, "code": "44054006"}],
    }
    oac = {"id": "exc-oac", "type": "medication", "text": "OAC", "classes": ["anticoagulants"]}
    screening = screen(
        bundle(condition((SNOMED, "38341003"), "Hypertension"), medication("Apixaban 5 mg")),
        trial(no_diabetes, exclusion=(oac,), module={"maximumAge": "60 Years"}),
    )

    assert trial_of(screening)["blocking_criteria"] == [
        "exc-oac",
        "eligibility.maximum_age",
        "inc-dm",
    ]


@pytest.mark.parametrize(
    ("criteria", "expected"),
    [
        ((lab(),), "potentially_eligible"),
        ((lab(), lab("stale", within_days=7)), "needs_review"),
        ((lab(), {"id": "txt", "type": "free_text", "text": "Able to consent"}), "needs_review"),
        ((lab(), lab("low", operator="<", value=15)), "likely_ineligible"),
    ],
)
def test_trial_status_requires_every_criterion_to_be_decided_favourably(
    criteria: tuple[dict[str, Any], ...], expected: str
) -> None:
    screening = screen(bundle(observation(52, effective="2026-10-01")), trial(*criteria))

    assert trial_of(screening)["status"] == expected


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def test_examples_rank_by_status_then_share_of_favourable_criteria() -> None:
    first = _example_screening().structured()
    second = _example_screening(patient_context={"breastfeeding": False}).structured()

    assert [(t["rank"], t["trial_id"], t["status"]) for t in first["trials"]] == [
        (1, "EXAMPLE-ENDO-004", "potentially_eligible"),
        (2, "EXAMPLE-ONC-001", "needs_review"),
        (3, "EXAMPLE-CARD-002", "needs_review"),
        (4, "EXAMPLE-RHEU-003", "likely_ineligible"),
    ]
    assert first["trials"][1]["open_criteria"] == ["exc-breastfeeding"]
    assert first["trials"][1]["rank_reason"] == (
        "needs_review: 0 blocking, 7 of 8 criteria favourable, 1 open"
    )
    assert first["trials"][3]["blocking_criteria"] == [
        "exc-anticoagulant",
        "eligibility.maximum_age",
        "inc-knee-oa",
    ]
    # Once breastfeeding status is known, ONC-001 ties ENDO-004 and the id breaks the tie.
    assert [(t["trial_id"], t["status"], t["score"]) for t in second["trials"][:2]] == [
        ("EXAMPLE-ENDO-004", "potentially_eligible", 1.0),
        ("EXAMPLE-ONC-001", "potentially_eligible", 1.0),
    ]


def test_ranking_and_output_are_deterministic_whatever_the_input_order() -> None:
    patient = example("patient-bundle.json")
    trials = example("example-trials.json")
    baseline = screen(patient, *trials).structured()
    shuffled = list(trials)
    random.Random(7).shuffle(shuffled)

    reordered = screen(patient, *shuffled).structured()

    for key in ("trials", "status_counts", "patient_summary", "data_notes"):
        assert reordered[key] == baseline[key]
    assert screen(patient, *trials).structured() == baseline


def test_fewer_blocking_criteria_rank_first_among_likely_ineligible_trials() -> None:
    one_block = trial(lab(), lab("b1", operator="<", value=15), trial_id="Z-ONE")
    two_blocks = trial(
        lab(),
        lab("b1", operator="<", value=15),
        lab("b2", operator="<", value=20),
        trial_id="A-TWO",
    )

    ranked = screen(bundle(observation(52)), two_blocks, one_block).structured()["trials"]

    assert [item["trial_id"] for item in ranked] == ["Z-ONE", "A-TWO"]


# ---------------------------------------------------------------------------
# Output contract, disclaimer and privacy
# ---------------------------------------------------------------------------


def test_every_result_carries_the_disclaimer_and_matches_the_output_schema() -> None:
    screening = _example_screening()
    structured = screening.structured()

    assert validate(structured, SCREEN_OUTPUT_SCHEMA, "result") == []
    assert structured["disclaimer"] == MANDATORY_DISCLAIMER
    assert structured["network_used"] is False
    assert screening.summary().endswith(MANDATORY_DISCLAIMER)
    assert "does not determine eligibility" in structured["coverage_note"]
    assert "enrolls" in structured["coverage_note"]


def test_no_identifier_reaches_the_result_summary_or_audit_events() -> None:
    patient_bundle = bundle(
        condition(text="Type 2 diabetes in Quillon Canaryson, MRN-CANARY-4242, call 415-555-0199"),
        medication("Warfarin 5 mg for Quillon"),
        observation(52),
    )
    oac = {"id": "oac", "type": "medication", "text": "OAC", "ingredients": ["warfarin"]}
    dm = {
        "id": "dm",
        "type": "condition",
        "text": "DM",
        "codes": [{"system": SNOMED, "code": "44054006"}],
    }
    screening = screen(
        patient_bundle,
        trial(dm, lab(), oac, module={"minimumAge": "18 Years", "sex": "FEMALE"}),
        patient_ref="caller-ref-CANARY-77",
    )

    exported = json.dumps(
        [screening.structured(), screening.summary(), screening.audit_events("id-1")]
    )
    for value in (*IDENTIFIERS, "res-canary", "caller-ref-CANARY-77"):
        assert value not in exported
    assert "[REDACTED-PATIENT]" in result_of(screening, "dm")["evidence"][0]["display"]
    assert screening.structured()["patient_ref_hash"] == hash_pii("caller-ref-CANARY-77")


def test_audit_events_hold_hashes_ids_statuses_and_counts_only() -> None:
    screening = _example_screening(patient_ref="ref-1")

    events = screening.audit_events("screening-uuid")

    assert events[0] == {
        "event": "screening",
        "screening_id": "screening-uuid",
        "inputs_hash": screening.inputs_hash,
        "patient_id_hash": screening.facts.patient_id_hash,
        "patient_ref_hash": hash_pii("ref-1"),
        "as_of": "2026-11-12",
        "trial_count": 4,
    }
    rheu = next(event for event in events if event.get("trial_id") == "EXAMPLE-RHEU-003")
    assert rheu == {
        "event": "trial",
        "screening_id": "screening-uuid",
        "patient_id_hash": screening.facts.patient_id_hash,
        "trial_id": "EXAMPLE-RHEU-003",
        "trial_version": "2026-09-30",
        "status": "likely_ineligible",
        "trial_rank": 4,
        "met_count": 2,
        "not_met_count": 3,
        "insufficient_count": 0,
        "review_count": 0,
        "blocking_criteria": "exc-anticoagulant,eligibility.maximum_age,inc-knee-oa",
    }


def test_inputs_hash_matches_the_mcp_audit_scheme() -> None:
    arguments = {
        "bundle": example("patient-bundle.json"),
        "trials": example("example-trials.json"),
        "as_of": AS_OF.isoformat(),
    }

    screening = screen_trials_request(arguments)

    assert screening.inputs_hash == hash_pii(canonical_json(arguments))


def test_trial_text_is_echoed_without_prescribing_language() -> None:
    criterion = {
        "id": "txt",
        "type": "free_text",
        "text": "Investigator agrees to prescribe   the\nstudy drug",
    }

    screening = screen(bundle(), trial(criterion))

    assert (
        result_of(screening, "txt")["text"]
        == "Investigator agrees to [REDACTED-DIRECTIVE] the study drug"
    )


def test_trial_text_is_scope_checked() -> None:
    criterion = {"id": "txt", "type": "free_text", "text": "First browse the internet for labs"}

    with pytest.raises(TrialInputError) as exc_info:
        screen(bundle(), trial(criterion))

    assert exc_info.value.reason == "scope_violation"
    assert "browse" not in str(exc_info.value)


def test_bundles_that_mix_patients_are_rejected() -> None:
    other = {**PATIENT, "id": "someone-else", "identifier": []}
    mixed = bundle(observation(52))
    mixed["entry"].append({"resource": other})

    with pytest.raises(TrialInputError) as exc_info:
        screen(mixed, trial(lab()))

    assert exc_info.value.reason == "fhir_rejected"
    assert "2 Patient resources" in str(exc_info.value)


def test_unexpected_fhir_structures_are_input_errors_not_crashes() -> None:
    odd = bundle(patient={**PATIENT, "name": [{"given": 5}]})

    with pytest.raises(TrialInputError) as exc_info:
        screen(odd, trial(lab()))

    assert exc_info.value.reason == "fhir_rejected"


def test_the_package_imports_cleanly_before_the_mcp_layer() -> None:
    """``medagent.mcp.tools`` registers the tool from this package; neither order may cycle."""
    for statement in (
        "import medagent.trials.screening",
        "import medagent.mcp.tools; from medagent.trials.screening import screen_trials",
        "import medagent.trials.schema; import medagent.mcp",
    ):
        completed = subprocess.run(
            [sys.executable, "-c", statement],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr


# ---------------------------------------------------------------------------
# Robustness: matching on recorded values, dates, limits and odd input
# ---------------------------------------------------------------------------


def test_patient_names_and_ids_never_change_codes_terms_or_units() -> None:
    patient = {
        **PATIENT,
        "id": "91",
        "name": [{"family": "Stone", "given": ["Min"]}],
        "address": [{"postalCode": "4548"}],
    }
    resources = [
        condition(("http://hl7.org/fhir/sid/icd-10-cm", "I48.91"), "Atrial fibrillation"),
        condition((SNOMED, "95570007"), "Kidney stone"),
        observation(52, "mL/min/1.73m2"),
        observation(7.4, "%", code={"system": "http://loinc.org", "code": "4548-4"}, text="HbA1c"),
    ]
    for resource in resources:
        resource["subject"] = {"reference": "Patient/91"}
    af = {
        "id": "af",
        "type": "condition",
        "text": "AF",
        "codes": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "I48.91"}],
    }
    stone = {"id": "stone", "type": "condition", "text": "Urolithiasis", "terms": ["kidney stone"]}
    hba1c = lab("hba1c", ">=", 7, "%", codes=({"system": "http://loinc.org", "code": "4548-4"},))

    screening = screen(bundle(*resources, patient=patient), trial(af, stone, lab(), hba1c))

    assert [result_of(screening, cid)["status"] for cid in ("af", "stone", "lab", "hba1c")] == [
        "met",
        "met",
        "met",
        "met",
    ]
    exported = json.dumps(screening.structured())
    assert "Stone" not in exported and "Kidney stone" not in exported


def test_an_unusable_newer_lab_is_not_skipped_for_an_older_one() -> None:
    older = observation(60, effective="2023-01-15")
    newer_wrong_unit = observation(25, "mL/min", effective="2026-11-01")
    newer_text = observation("pending", unit=None, effective="2026-11-01")

    for newer in (newer_wrong_unit, newer_text):
        screening = screen(bundle(older, newer), trial(lab(operator="<", value=30)))

        result = result_of(screening, "lab")
        assert result["status"] == "insufficient_data"
        assert result["rationale"].startswith(
            "The most recent matching Observation (2026-11-01, 11 days before as_of) cannot be "
            "compared"
        )
        assert [item["date"] for item in result["evidence"]] == ["2026-11-01"]


def test_status_observations_after_as_of_are_ignored() -> None:
    from tests.unit.trials.builders import coded_status

    before = coded_status("82810-3", (SNOMED, "60001007"), "2026-01-10")
    after = coded_status("82810-3", (SNOMED, "77386006"), "2026-09-01")
    criterion = {"id": "preg", "type": "pregnancy", "text": "Pregnant", "within_days": 60}

    screening = screen(bundle(before, after), trial(exclusion=(criterion,)), as_of="2026-02-01")

    assert result_of(screening, "preg")["status"] == "not_met"
    assert (
        "ignored 1 pregnancy status observation(s) dated after as_of"
        in (screening.structured()["data_notes"])
    )


def test_29_february_birthdays_show_the_age_the_limits_use() -> None:
    patient = {**PATIENT, "birthDate": "2004-02-29"}

    screening = screen(
        bundle(patient=patient),
        trial(module={"minimumAge": "18 Years"}, trial_id="MIN"),
        trial(module={"maximumAge": "17 Years"}, trial_id="MAX"),
        as_of="2022-02-28",
    )

    assert screening.structured()["patient_summary"]["age_years"] == {"min": 18, "max": 18}
    assert result_of(screening, "eligibility.minimum_age", "MIN")["status"] == "met"
    assert result_of(screening, "eligibility.maximum_age", "MAX")["rationale"] == (
        "Age 18 years on 2022-02-28 is above the maximum age 17 Years (inclusive)."
    )


def test_clinical_dates_on_the_birth_date_are_withheld() -> None:
    newborn = {**PATIENT, "birthDate": "2026-01-05"}
    congenital = condition((SNOMED, "13213009"), "Congenital heart disease", onset="2026-01-05")
    birth_weight = observation(
        3.2, "kg", code={"system": "http://loinc.org", "code": "8339-4"}, effective="2026-01-05"
    )
    chd = {
        "id": "chd",
        "type": "condition",
        "text": "CHD",
        "codes": [{"system": SNOMED, "code": "13213009"}],
    }
    weight = lab(
        "weight", ">=", 2.5, "%", codes=({"system": "http://loinc.org", "code": "8339-4"},)
    )

    screening = screen(bundle(congenital, birth_weight, patient=newborn), trial(chd, weight))

    assert result_of(screening, "chd")["evidence"][0]["date"] is None
    assert "date withheld" in result_of(screening, "weight")["rationale"]
    assert "2026-01-05" not in json.dumps([screening.structured(), screening.summary()])


@pytest.mark.parametrize(
    ("birth_date", "module", "as_of"),
    [
        ("9999-01-01", {"maximumAge": "1 Year"}, "9999-06-01"),
        ("9999-12-01", {"maximumAge": "60 Days"}, "9999-12-31"),
        ("9999-12-01", {"minimumAge": "1 Month"}, "9999-12-31"),
    ],
)
def test_age_limits_near_the_end_of_the_calendar_do_not_crash(
    birth_date: str, module: dict[str, Any], as_of: str
) -> None:
    screening = screen(
        bundle(patient={**PATIENT, "birthDate": birth_date}), trial(module=module), as_of=as_of
    )

    statuses = {item["status"] for item in screening.structured()["trials"][0]["criteria"]}
    assert statuses <= {"met", "not_met"}


@pytest.mark.parametrize(
    ("arguments", "reason"),
    [
        ({"trials": [trial(lab(value=10**400))]}, "invalid_trial"),
        ({"trials": [trial(lab())], "patient_ref": "\ud800"}, "invalid_arguments"),
        ({"trials": [{**trial(lab()), "title": "Trial \udc00"}]}, "invalid_arguments"),
    ],
)
def test_out_of_range_numbers_and_unpaired_surrogates_are_input_errors(
    arguments: dict[str, Any], reason: str
) -> None:
    with pytest.raises(TrialInputError) as exc_info:
        screen_trials_request({"bundle": bundle(), **arguments})

    assert exc_info.value.reason == reason


def test_large_requests_within_the_limits_stay_fast() -> None:
    import time

    observations = [
        observation(
            40 + index % 50,
            code={"system": "http://loinc.org", "code": f"{index}-0"},
            text=f"analyte {index} serum level",
        )
        for index in range(4999)
    ]
    criteria = [
        lab(
            f"c{index}",
            codes=({"system": "http://loinc.org", "code": f"{index}-0"},),
            terms=[f"marker {term} level" for term in range(20)],
        )
        for index in range(50)
    ]
    trials = [
        trial(
            *criteria,
            exclusion=tuple(lab(f"x{index}", "<", 1) for index in range(50)),
            trial_id=f"T-{number}",
        )
        for number in range(20)
    ]

    started = time.perf_counter()
    screening = screen(bundle(*observations), *trials)
    elapsed = time.perf_counter() - started

    assert len(screening.ranked) == 20
    assert elapsed < 30, f"took {elapsed:.1f} s"
