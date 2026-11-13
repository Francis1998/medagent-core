"""Tool-level tests for the medagent MCP server: semantics, schemas and safety."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

import pytest
import structlog
from structlog.testing import capture_logs

from medagent.extraction import fhir_parser
from medagent.mcp import tools as mcp_tools
from medagent.mcp.schema import validate
from medagent.mcp.tools import (
    TOOLS,
    TOOLS_BY_NAME,
    ToolInputError,
    ToolOutput,
    interaction_checks,
    safety_control_catalog,
)
from medagent.safety import scope_enforcer
from medagent.safety.disclaimer import MANDATORY_DISCLAIMER
from medagent.safety.pii_hasher import hash_pii

TOOL_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")

FHIR_BUNDLE: dict[str, Any] = {
    "resourceType": "Bundle",
    "type": "collection",
    "entry": [
        {
            "resource": {
                "resourceType": "Patient",
                "id": "pat-1",
                "identifier": [{"system": "urn:mrn", "value": "MRN-0042"}],
                "name": [{"family": "Doe", "given": ["Janet"]}],
                "birthDate": "1944-03-02",
                "gender": "female",
                "telecom": [{"system": "phone", "value": "415-555-0101"}],
            }
        },
        {
            "resource": {
                "resourceType": "Condition",
                "code": {"text": "Atrial fibrillation; call 415-555-0101 on 2024-01-15"},
            }
        },
        {
            "resource": {
                "resourceType": "MedicationRequest",
                "status": "active",
                "medicationCodeableConcept": {
                    "text": "Warfarin 5 mg tablet",
                    "coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm"}],
                },
                "dosageInstruction": [{"text": "5 mg", "timing": {"code": {"text": "daily"}}}],
            }
        },
        {
            "resource": {
                "resourceType": "MedicationRequest",
                "status": "active",
                "medicationCodeableConcept": {"text": "Ibuprofen 400 mg tablet"},
            }
        },
        {
            "resource": {
                "resourceType": "MedicationRequest",
                "status": "stopped",
                "medicationCodeableConcept": {"text": "Naproxen 250 mg tablet"},
            }
        },
        {
            "resource": {
                "resourceType": "Observation",
                "code": {"text": "eGFR"},
                "valueQuantity": {"value": 28, "unit": "mL/min/1.73m2"},
            }
        },
        {
            "resource": {
                "resourceType": "Observation",
                "code": {"text": "eGFR"},
                "valueQuantity": {"value": 41, "unit": "mL/min/1.73m2"},
            }
        },
        {
            "resource": {
                "resourceType": "AllergyIntolerance",
                "code": {"text": "Penicillin"},
            }
        },
    ],
}


def run(name: str, arguments: dict[str, Any]) -> ToolOutput:
    """Validate arguments like the server does, then run the tool handler."""
    tool = TOOLS_BY_NAME[name]
    assert validate(arguments, tool.input_schema) == []
    output = tool.handler(arguments)
    assert validate(output.structured, tool.output_schema, "result") == []
    return output


# ---------------------------------------------------------------------------
# Schema validator and tool definitions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("instance", "message"),
    [
        ({"medications": [True]}, "arguments.medications[0] must be of type object or string"),
        ({"medications": ["  "]}, "arguments.medications[0] must match pattern"),
        ({"medications": [{"dose": "5 mg"}]}, "arguments.medications[0].name is required"),
        ({"medications": ["x"], "patient": {"age": True}}, "arguments.patient.age must be of type"),
        ({"medications": ["x"], "patient": {"age": 151}}, "arguments.patient.age must be <= 150"),
        (
            {"medications": ["x"], "patient": {"hepatic_function": "C"}},
            "arguments.patient.hepatic_function must be one of",
        ),
        ({"medications": ["x"], "extra": 1}, "arguments has unexpected properties"),
    ],
)
def test_input_validation_reports_actionable_paths(instance: Any, message: str) -> None:
    errors = validate(instance, TOOLS_BY_NAME["screen_medications"].input_schema)

    assert any(error.startswith(message) for error in errors), errors


def test_tool_definitions_are_well_formed_and_sorted() -> None:
    names = [tool.name for tool in TOOLS]

    assert names == sorted(names)
    assert len(set(names)) == len(names)
    for tool in TOOLS:
        definition = tool.definition()
        assert TOOL_NAME.match(definition["name"])
        assert definition["inputSchema"]["type"] == "object"
        assert definition["inputSchema"]["additionalProperties"] is False
        assert definition["outputSchema"]["properties"]["disclaimer"]["const"] == (
            MANDATORY_DISCLAIMER
        )
        json.dumps(definition)


def test_interaction_rules_are_offline_discovered_and_unique() -> None:
    checks = interaction_checks()
    ids = [check.id for check in checks]

    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)
    assert {"qtc_ddi", "anticoag_bleeding", "triple_whammy", "warfarin_nsaid"} <= set(ids)
    assert len(checks) >= 80
    assert all(check.category == "interaction" for check in checks)


# ---------------------------------------------------------------------------
# screen_medications
# ---------------------------------------------------------------------------


def test_screen_combines_patient_context_list_and_interaction_checks() -> None:
    output = run(
        "screen_medications",
        {
            "medications": ["warfarin 5 mg", {"name": "ibuprofen", "dosage": "400 mg"}],
            "patient": {"age": 81, "egfr": 25, "allergies": ["sulfa"]},
        },
    )
    result = output.structured

    check_ids = {finding["check_id"] for finding in result["findings"]}
    assert {"warfarin_nsaid", "renal_dose", "black_box_warning"} <= check_ids
    severities = [finding["severity"] for finding in result["findings"]]
    order = ["CRITICAL", "HIGH", "MODERATE", "LOW", "UNKNOWN"]
    assert severities == sorted(severities, key=order.index)
    assert result["highest_severity"] == severities[0]
    assert result["escalation_recommended"] is True
    assert (
        result["finding_count"]
        == len(result["findings"])
        == sum(result["severity_counts"].values())
    )
    assert {"allergy", "beers_criteria", "renal_dose", "duplicate_therapy"} <= set(
        result["checks_run"]
    )
    assert result["checks_skipped"] == [
        {"check_id": "pregnancy", "missing": ["pregnant"]},
        {"check_id": "lactation", "missing": ["breastfeeding"]},
        {"check_id": "hepatic_dose", "missing": ["hepatic_function"]},
    ]
    assert result["interaction_rules_evaluated"] == len(interaction_checks())
    assert result["network_used"] is False
    assert result["patient_ref_hash"] is None
    assert MANDATORY_DISCLAIMER in output.summary
    assert "Not run, missing patient context: pregnancy (needs pregnant)" in output.summary


def test_screen_flags_allergy_and_pregnancy_when_context_is_supplied() -> None:
    result = run(
        "screen_medications",
        {
            "medications": ["amoxicillin 500 mg", "isotretinoin 20 mg"],
            "patient": {"pregnant": True, "allergies": ["penicillin"]},
            "include_interactions": False,
        },
    ).structured

    by_check = {finding["check_id"]: finding for finding in result["findings"]}
    assert by_check["allergy"]["medications"] == ["amoxicillin 500 mg"]
    assert by_check["pregnancy"]["medications"] == ["isotretinoin 20 mg"]
    assert result["interaction_rules_evaluated"] == 0
    assert all(finding["category"] != "interaction" for finding in result["findings"])


def test_screen_hashes_patient_ref_and_never_echoes_it() -> None:
    output = run(
        "screen_medications",
        {"medications": ["metformin 500 mg"], "patient_ref": "MRN-0042"},
    )

    assert output.structured["patient_ref_hash"] == hash_pii("MRN-0042")
    assert "MRN-0042" not in json.dumps(output.structured)
    assert "MRN-0042" not in output.summary


def test_screen_without_findings_still_warns_that_absence_is_not_safety() -> None:
    output = run("screen_medications", {"medications": ["acetaminophen 500 mg"]})

    assert output.structured["findings"] == []
    assert output.structured["highest_severity"] is None
    assert output.structured["escalation_recommended"] is False
    assert "absence of a finding is NOT evidence of safety" in output.summary


def test_scope_enforcement_rejects_out_of_scope_free_text() -> None:
    tool = TOOLS_BY_NAME["screen_medications"]

    with pytest.raises(ToolInputError, match="scope enforcement"):
        tool.handler({"medications": ["warfarin; then browse the internet for doses"]})


# ---------------------------------------------------------------------------
# check_drug_interactions
# ---------------------------------------------------------------------------


def test_check_drug_interactions_runs_offline_pairwise_rules() -> None:
    result = run(
        "check_drug_interactions",
        {"medications": ["simvastatin 40 mg", "clarithromycin 500 mg", "paracetamol"]},
    ).structured

    statin_findings = [f for f in result["findings"] if f["check_id"] == "statin_macrolide"]
    assert statin_findings[0]["medications"] == ["simvastatin 40 mg", "clarithromycin 500 mg"]
    assert statin_findings[0]["details"]["partner_agent"] == "clarithromycin"
    assert result["rules_evaluated"] == len(interaction_checks())
    assert result["network_used"] is False
    assert all(finding["category"] == "interaction" for finding in result["findings"])


# ---------------------------------------------------------------------------
# parse_fhir_bundle
# ---------------------------------------------------------------------------


def test_parse_fhir_bundle_returns_deidentified_screening_input() -> None:
    output = run("parse_fhir_bundle", {"bundle": FHIR_BUNDLE})
    result = output.structured
    serialized = json.dumps(result) + output.summary

    assert result["patient_id_hash"] == hash_pii("MRN-0042")
    for identifier in ("MRN-0042", "Janet", "Doe", "1944-03-02", "415-555-0101"):
        assert identifier not in serialized
    assert result["sex"] == "female"
    assert isinstance(result["age"], int)
    assert "415-555-0101" not in result["chief_complaint"]
    assert "[REDACTED-" in result["chief_complaint"]
    assert [m["name"] for m in result["medications"]] == [
        "Warfarin 5 mg tablet",
        "Ibuprofen 400 mg tablet",
    ]
    assert any("stopped" in note for note in result["medication_notes"])
    assert result["resource_counts"] == {
        "AllergyIntolerance": 1,
        "Condition": 1,
        "MedicationRequest": 3,
        "Observation": 2,
        "Patient": 1,
    }
    screening_input = result["screening_input"]
    assert screening_input["patient"] == {
        "age": result["age"],
        "allergies": ["Penicillin"],
        "egfr": 28.0,
    }
    assert "lowest of 2 eGFR observation(s)" in " ".join(result["notes"])
    assert result["screening_input_issues"] == []

    screen = run("screen_medications", screening_input).structured
    assert "warfarin_nsaid" in {finding["check_id"] for finding in screen["findings"]}


def test_parse_fhir_bundle_ignores_non_finite_egfr_values() -> None:
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p"}},
            {
                "resource": {
                    "resourceType": "Observation",
                    "code": {"text": "eGFR"},
                    "valueString": "NaN",
                }
            },
        ],
    }

    result = run("parse_fhir_bundle", {"bundle": bundle}).structured

    assert "egfr" not in result["screening_input"]["patient"]
    json.dumps(result, allow_nan=False)


def test_parse_fhir_bundle_rejects_malformed_resources() -> None:
    bundle = {"resourceType": "Bundle", "entry": [{"resource": {"resourceType": "Patient"}}]}
    bundle["entry"][0]["resource"]["identifier"] = "not-a-list"

    with pytest.raises(ToolInputError, match="unexpected structure"):
        TOOLS_BY_NAME["parse_fhir_bundle"].handler({"bundle": bundle})


def test_parse_fhir_bundle_schema_requires_a_bundle_resource() -> None:
    errors = validate(
        {"bundle": {"resourceType": "Patient"}}, TOOLS_BY_NAME["parse_fhir_bundle"].input_schema
    )

    assert errors == ["arguments.bundle.resourceType must equal 'Bundle'"]


# ---------------------------------------------------------------------------
# list_safety_controls
# ---------------------------------------------------------------------------


def test_list_safety_controls_covers_constraints_and_checks() -> None:
    result = run("list_safety_controls", {}).structured

    assert result["count"] == len(safety_control_catalog()) == len(result["controls"])
    counts = result["counts_by_category"]
    assert counts["platform"] == 8
    assert counts["patient_context"] == 7
    assert counts["medication_list"] == 6
    assert counts["interaction"] == len(interaction_checks())
    ids = {control["id"] for control in result["controls"]}
    assert {"mandatory_disclaimer", "scope_enforcement", "allergy", "warfarin_nsaid"} <= ids


def test_list_safety_controls_filters_by_category_and_query() -> None:
    platform = run("list_safety_controls", {"category": "platform"}).structured
    warfarin = run("list_safety_controls", {"query": "WARFARIN"}).structured

    assert {control["category"] for control in platform["controls"]} == {"platform"}
    assert platform["counts_by_category"]["interaction"] == 0
    assert "warfarin_nsaid" in {control["id"] for control in warfarin["controls"]}
    assert all("warfarin" in json.dumps(control).lower() for control in warfarin["controls"])


# ---------------------------------------------------------------------------
# De-identification, FHIR robustness and logging (review follow-ups)
# ---------------------------------------------------------------------------


@pytest.fixture()
def safety_logs(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, Any]]]:
    """Capture structlog events from the modules the MCP tools call into."""
    with capture_logs() as logs:
        for module in (mcp_tools, fhir_parser, scope_enforcer):
            monkeypatch.setattr(module, "logger", structlog.get_logger(module.__name__))
        yield logs


def _bundle(*resources: dict[str, Any]) -> dict[str, Any]:
    return {"resourceType": "Bundle", "entry": [{"resource": r} for r in resources]}


PATIENT = {"resourceType": "Patient", "id": "p1", "birthDate": "1950-01-01"}


def test_screen_redacts_identifiers_in_medication_and_allergy_text() -> None:
    output = run(
        "screen_medications",
        {
            "medications": ["warfarin 5 mg; call 415-555-0101", "ibuprofen 400 mg"],
            "patient": {"allergies": ["penicillin; contact patient@example.com"]},
        },
    )
    exported = json.dumps(output.structured) + output.summary

    assert "415-555-0101" not in exported
    assert "patient@example.com" not in exported
    assert "warfarin_nsaid" in {finding["check_id"] for finding in output.structured["findings"]}


def test_parse_fhir_bundle_redacts_every_exported_free_text_field() -> None:
    bundle = _bundle(
        PATIENT,
        {
            "resourceType": "MedicationRequest",
            "status": "active",
            "medicationCodeableConcept": {"text": "Warfarin 5 mg"},
            "dosageInstruction": [{"text": "5 mg daily, questions: 415-555-0101"}],
        },
        {
            "resourceType": "Observation",
            "code": {"text": "Social note"},
            "valueString": "SSN 123-45-6789",
        },
        {"resourceType": "AllergyIntolerance", "code": {"text": "Penicillin (jd@example.com)"}},
    )

    exported = json.dumps(run("parse_fhir_bundle", {"bundle": bundle}).structured)

    for identifier in ("415-555-0101", "123-45-6789", "jd@example.com"):
        assert identifier not in exported


@pytest.mark.parametrize("separator", [" ", "\n", "\t"])
def test_directive_language_in_source_text_is_redacted(separator: str) -> None:
    bundle = _bundle(
        PATIENT,
        {
            "resourceType": "MedicationRequest",
            "status": "active",
            "medicationCodeableConcept": {"text": "Enoxaparin"},
            "dosageInstruction": [{"text": f"Administer{separator}40 mg nightly"}],
        },
    )

    result = run("parse_fhir_bundle", {"bundle": bundle}).structured

    assert result["medications"][0]["dosage"] == "[REDACTED-DIRECTIVE] nightly"


@pytest.mark.parametrize("dose", ["0.4", ".5", "0,5", "2.5"])
def test_decimal_dose_directive_in_source_text_is_redacted(dose: str) -> None:
    bundle = _bundle(
        PATIENT,
        {
            "resourceType": "MedicationRequest",
            "status": "active",
            "medicationCodeableConcept": {"text": "Lorazepam"},
            "dosageInstruction": [{"text": f"Administer {dose} mg nightly"}],
        },
    )

    result = run("parse_fhir_bundle", {"bundle": bundle}).structured

    assert result["medications"][0]["dosage"] == "[REDACTED-DIRECTIVE] nightly"


def test_egfr_units_are_normalised_and_unknown_units_skipped() -> None:
    def egfr(value: float, unit: str | None) -> dict[str, Any]:
        quantity: dict[str, Any] = {"value": value}
        if unit is not None:
            quantity["unit"] = unit
        return {"resourceType": "Observation", "code": {"text": "eGFR"}, "valueQuantity": quantity}

    bundle = _bundle(
        PATIENT,
        egfr(0.5, "mL/s/1.73m2"),
        egfr(45, "mL/min/{1.73_m2}"),
        egfr(12, "mg/dL"),
        egfr(9, None),
    )

    result = run("parse_fhir_bundle", {"bundle": bundle}).structured

    assert result["screening_input"]["patient"]["egfr"] == 30.0
    notes = " ".join(result["notes"])
    assert "lowest of 2" in notes
    assert "skipped 2 eGFR observation(s) with missing or unsupported units" in notes


def test_multi_patient_bundles_are_rejected() -> None:
    second = {"resourceType": "Patient", "id": "p2"}

    with pytest.raises(ToolInputError, match="2 Patient resources"):
        TOOLS_BY_NAME["parse_fhir_bundle"].handler({"bundle": _bundle(PATIENT, second)})


def test_resources_for_another_patient_are_rejected() -> None:
    foreign = {
        "resourceType": "MedicationRequest",
        "status": "active",
        "subject": {"reference": "Patient/p2"},
        "medicationCodeableConcept": {"text": "Warfarin"},
    }
    own = {**foreign, "subject": {"reference": "Patient/p1"}}

    assert run("parse_fhir_bundle", {"bundle": _bundle(PATIENT, own)}).structured["medications"]
    with pytest.raises(ToolInputError, match="different patient"):
        TOOLS_BY_NAME["parse_fhir_bundle"].handler({"bundle": _bundle(PATIENT, foreign)})


def test_medication_status_policy_keeps_current_therapy_by_default() -> None:
    def med(resource_type: str, status: str | None, name: str) -> dict[str, Any]:
        resource: dict[str, Any] = {
            "resourceType": resource_type,
            "medicationCodeableConcept": {"text": name},
        }
        if status is not None:
            resource["status"] = status
        return resource

    bundle = _bundle(
        PATIENT,
        med("MedicationRequest", "active", "Warfarin"),
        med("MedicationRequest", "on-hold", "Metformin"),
        med("MedicationRequest", "completed", "Amoxicillin"),
        med("MedicationRequest", "draft", "Ibuprofen"),
        med("MedicationRequest", None, "Digoxin"),
        med("MedicationStatement", "not-taken", "Aspirin"),
        med("MedicationStatement", "intended", "Fluconazole"),
        med("MedicationStatement", "active", "Omeprazole"),
    )

    current = run("parse_fhir_bundle", {"bundle": bundle}).structured
    proposed = run("parse_fhir_bundle", {"bundle": bundle, "include_proposed": True}).structured

    assert [m["name"] for m in current["medications"]] == ["Warfarin", "Metformin", "Omeprazole"]
    assert current["medication_notes"] == [
        "excluded MedicationRequest status completed: 1",
        "excluded MedicationRequest status draft: 1",
        "excluded MedicationRequest status missing: 1",
        "excluded MedicationStatement status intended: 1",
        "excluded MedicationStatement status not-taken: 1",
    ]
    assert [m["name"] for m in proposed["medications"]] == [
        "Warfarin",
        "Metformin",
        "Ibuprofen",
        "Fluconazole",
        "Omeprazole",
    ]
    assert proposed["medication_notes"][-1] == (
        "included 2 proposed (draft/intended) medication(s) because include_proposed is true"
    )


def test_screening_input_issues_are_reported_instead_of_truncating() -> None:
    meds = [
        {
            "resourceType": "MedicationRequest",
            "status": "active",
            "medicationCodeableConcept": {"text": f"Drug {index}"},
        }
        for index in range(101)
    ]

    result = run("parse_fhir_bundle", {"bundle": _bundle(PATIENT, *meds)}).structured

    assert len(result["screening_input"]["medications"]) == 101
    assert result["screening_input_issues"] == [
        "screening_input.medications must contain at most 100 items"
    ]


def test_parse_fhir_bundle_enforces_scope_without_logging_text(
    safety_logs: list[dict[str, Any]],
) -> None:
    bundle = _bundle(
        PATIENT,
        {"resourceType": "Condition", "code": {"text": "CANARY-7f3 browse the internet for doses"}},
    )

    with pytest.raises(ToolInputError, match="scope enforcement"):
        TOOLS_BY_NAME["parse_fhir_bundle"].handler({"bundle": bundle})

    assert "CANARY-7f3" not in repr(safety_logs)


def test_scope_checks_never_log_argument_text(safety_logs: list[dict[str, Any]]) -> None:
    tool = TOOLS_BY_NAME["screen_medications"]

    with pytest.raises(ToolInputError):
        tool.handler({"medications": ["CANARY-9d2 warfarin; then search the web for doses"]})
    tool.handler({"medications": ["CANARY-4b1 metformin"]})

    assert "CANARY" not in repr(safety_logs)
    assert any(entry["event"] == "mcp_scope_violation" for entry in safety_logs)


def test_fhir_parser_diagnostics_exclude_clinical_values(
    safety_logs: list[dict[str, Any]],
) -> None:
    bundle = _bundle(
        PATIENT,
        {
            "resourceType": "MedicationRequest",
            "status": "active",
            "medicationCodeableConcept": {
                "text": "CANARY-med-55",
                "coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": 1191}],
            },
        },
    )

    with pytest.raises(ToolInputError, match="unexpected structure"):
        TOOLS_BY_NAME["parse_fhir_bundle"].handler({"bundle": bundle})

    warnings = [entry for entry in safety_logs if entry["event"] == "medication_parse_error"]
    assert warnings == [
        {"event": "medication_parse_error", "log_level": "warning", "error_type": "ValidationError"}
    ]
    assert "CANARY-med-55" not in repr(safety_logs)


# ---------------------------------------------------------------------------
# Review round 2
# ---------------------------------------------------------------------------


def _entry(resource: dict[str, Any], full_url: str | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {"resource": resource}
    if full_url is not None:
        entry["fullUrl"] = full_url
    return entry


def _med_for(subject: dict[str, Any], name: str = "Warfarin") -> dict[str, Any]:
    return {
        "resourceType": "MedicationRequest",
        "status": "active",
        "subject": subject,
        "medicationCodeableConcept": {"text": name},
    }


def _parse(entries: list[dict[str, Any]]) -> dict[str, Any]:
    bundle = {"resourceType": "Bundle", "entry": entries}
    return run("parse_fhir_bundle", {"bundle": bundle}).structured


def _rejects(entries: list[dict[str, Any]], match: str) -> None:
    bundle = {"resourceType": "Bundle", "entry": entries}
    with pytest.raises(ToolInputError, match=match):
        TOOLS_BY_NAME["parse_fhir_bundle"].handler({"bundle": bundle})


def test_absolute_references_must_match_the_patients_full_url() -> None:
    full_url = "https://ehr-a.example/fhir/Patient/p1"
    patient = _entry(PATIENT, full_url)

    assert _parse([patient, _entry(_med_for({"reference": full_url}))])["medications"]
    assert _parse([patient, _entry(_med_for({"reference": "Patient/p1"}))])["medications"]
    _rejects(
        [patient, _entry(_med_for({"reference": "https://ehr-b.example/fhir/Patient/p1"}))],
        "different patient",
    )


def test_unresolvable_references_fail_closed_when_a_patient_is_supplied() -> None:
    anonymous = {
        "resourceType": "Patient",
        "identifier": [{"system": "urn:mrn", "value": "MRN-1"}],
    }

    _rejects([_entry(anonymous), _entry(_med_for({"reference": "Patient/x"}))], "patient")
    by_identifier = _med_for({"identifier": {"system": "urn:mrn", "value": "MRN-1"}})
    assert _parse([_entry(anonymous), _entry(by_identifier)])["medications"]
    other = _med_for({"identifier": {"system": "urn:mrn", "value": "MRN-2"}})
    _rejects([_entry(anonymous), _entry(other)], "different patient")
    assert _parse([_entry(_med_for({"reference": "Patient/solo"}))])["medications"]


def test_entered_in_error_and_cancelled_resources_are_excluded() -> None:
    def egfr(value: float, status: str) -> dict[str, Any]:
        return {
            "resourceType": "Observation",
            "status": status,
            "code": {"text": "eGFR"},
            "valueQuantity": {"value": value, "unit": "mL/min/1.73m2"},
        }

    result = _parse(
        [
            _entry(PATIENT),
            _entry(egfr(90, "final")),
            _entry(egfr(20, "entered-in-error")),
            _entry(egfr(15, "cancelled")),
        ]
    )

    assert result["screening_input"]["patient"]["egfr"] == 90.0
    assert len(result["lab_results"]) == 1
    assert "excluded 2 invalidated resource(s)" in " ".join(result["notes"])


ALLERGY_CLINICAL = "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical"


def test_inactive_and_resolved_allergies_are_excluded_and_counted() -> None:
    def allergy(name: str, *codings: dict[str, Any]) -> dict[str, Any]:
        resource: dict[str, Any] = {"resourceType": "AllergyIntolerance", "code": {"text": name}}
        if codings:
            resource["clinicalStatus"] = {"coding": list(codings)}
        return resource

    result = _parse(
        [
            _entry(PATIENT),
            _entry(allergy("Penicillin", {"system": ALLERGY_CLINICAL, "code": "active"})),
            _entry(allergy("Sulfonamides", {"system": ALLERGY_CLINICAL, "code": "inactive"})),
            _entry(allergy("Codeine", {"code": "resolved"})),
            _entry(allergy("Latex")),
            _entry(
                allergy("Iodine", {"system": "urn:oid:2.16.840.1.113883.19", "code": "inactive"})
            ),
            _entry(
                allergy(
                    "Aspirin",
                    {"system": ALLERGY_CLINICAL, "code": "resolved"},
                    {"system": ALLERGY_CLINICAL, "code": "active"},
                )
            ),
        ]
    )

    kept = ["Penicillin", "Latex", "Iodine", "Aspirin"]
    assert result["allergies"] == kept
    assert result["screening_input"]["patient"]["allergies"] == kept
    assert (
        "excluded 2 AllergyIntolerance record(s) with clinicalStatus inactive or resolved"
        in " ".join(result["notes"])
    )


def test_do_not_perform_medication_requests_are_excluded_and_counted() -> None:
    def request(name: str, **fields: Any) -> dict[str, Any]:
        return {
            "resourceType": "MedicationRequest",
            "status": "active",
            "medicationCodeableConcept": {"text": name},
            **fields,
        }

    bundle = [
        _entry(PATIENT),
        _entry(request("Warfarin")),
        _entry(request("Ibuprofen", doNotPerform=True)),
        _entry(request("Aspirin", doNotPerform=False)),
        _entry(request("Naproxen", status="stopped", doNotPerform=True)),
        _entry(request("Ketorolac", status="draft", doNotPerform=True)),
    ]

    result = _parse(bundle)
    proposed = run(
        "parse_fhir_bundle",
        {"bundle": {"resourceType": "Bundle", "entry": bundle}, "include_proposed": True},
    ).structured

    assert [m["name"] for m in result["medications"]] == ["Warfarin", "Aspirin"]
    assert result["medication_notes"] == [
        "excluded MedicationRequest status draft: 1",
        "excluded MedicationRequest status stopped: 1",
        "excluded MedicationRequest doNotPerform true: 1",
    ]
    assert [m["name"] for m in proposed["medications"]] == ["Warfarin", "Aspirin"]
    assert proposed["medication_notes"] == [
        "excluded MedicationRequest status stopped: 1",
        "excluded MedicationRequest doNotPerform true: 2",
    ]


def test_medication_references_are_resolved_or_reported() -> None:
    resolvable = {
        "resourceType": "MedicationRequest",
        "status": "active",
        "medicationReference": {"reference": "Medication/m1"},
    }
    dangling = {**resolvable, "medicationReference": {"reference": "Medication/missing"}}
    medication = {"resourceType": "Medication", "id": "m1", "code": {"text": "Warfarin 5 mg"}}

    result = _parse([_entry(PATIENT), _entry(medication), _entry(resolvable), _entry(dangling)])

    assert [m["name"] for m in result["medications"]] == ["Warfarin 5 mg"]
    assert result["screening_input_issues"] == [
        "1 current medication(s) could not be named and are missing from screening_input; "
        "screening the list unchanged could miss interactions"
    ]


def test_known_patient_identifiers_are_redacted_from_clinical_text() -> None:
    patient = {
        "resourceType": "Patient",
        "id": "p1",
        "identifier": [{"value": "MRN-0042"}],
        "name": [{"given": ["Janet"], "family": "Doe"}],
    }
    condition = {"resourceType": "Condition", "code": {"text": "Janet Doe (MRN-0042) has AF"}}

    result = _parse([_entry(patient), _entry(condition)])
    exported = json.dumps(result)

    for identifier in ("Janet", "Doe", "MRN-0042"):
        assert identifier not in exported
    assert "[REDACTED-PATIENT]" in result["chief_complaint"]


def test_integral_floats_are_accepted_as_integers() -> None:
    schema = TOOLS_BY_NAME["screen_medications"].input_schema

    assert validate({"medications": ["x"], "patient": {"age": 81.0}}, schema) == []
    assert validate({"medications": ["x"], "patient": {"age": 81.5}}, schema) != []
    result = run(
        "screen_medications", {"medications": ["warfarin"], "patient": {"age": 81.0}}
    ).structured
    assert result["patient_context_used"]["age"] == 81
    assert isinstance(result["patient_context_used"]["age"], int)


def test_validation_errors_do_not_reflect_unknown_property_names() -> None:
    schema = TOOLS_BY_NAME["screen_medications"].input_schema

    errors = validate({"medications": ["x"], "administer 5 mg to jd@example.com": 1}, schema)

    assert errors == [
        "arguments has unexpected properties "
        "(allowed: include_interactions, medications, patient, patient_ref)"
    ]


def test_unrecognised_medication_statuses_are_not_echoed() -> None:
    bad_status = {
        "resourceType": "MedicationRequest",
        "status": "stopped; call 415-555-0101",
        "medicationCodeableConcept": {"text": "Warfarin"},
    }

    result = _parse([_entry(PATIENT), _entry(bad_status)])

    assert result["medication_notes"] == ["excluded MedicationRequest status unrecognized: 1"]
    assert "415-555-0101" not in json.dumps(result)


def test_medication_statement_dosage_is_kept() -> None:
    statement = {
        "resourceType": "MedicationStatement",
        "status": "active",
        "medicationCodeableConcept": {"text": "Omeprazole 20 mg"},
        "dosage": [
            {"text": "20 mg daily", "route": {"text": "oral"}, "timing": {"code": {"text": "QD"}}}
        ],
    }

    result = _parse([_entry(PATIENT), _entry(statement)])

    assert result["medications"] == [
        {"name": "Omeprazole 20 mg", "dosage": "20 mg daily", "route": "oral", "frequency": "QD"}
    ]


def test_unknown_resource_types_are_counted_without_echoing_them() -> None:
    odd = {"resourceType": "patient@example.com"}

    result = _parse([_entry(PATIENT), _entry(odd)])

    assert result["resource_counts"] == {"Other": 1, "Patient": 1}
    assert "patient@example.com" not in json.dumps(result)


# ---------------------------------------------------------------------------
# Review round 3
# ---------------------------------------------------------------------------

UNNAMED_ISSUE = (
    "1 current medication(s) could not be named and are missing from screening_input; "
    "screening the list unchanged could miss interactions"
)
RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
UCUM = "http://unitsofmeasure.org"
LOINC = "http://loinc.org"


def _egfr(quantity: dict[str, Any]) -> dict[str, Any]:
    return {"resourceType": "Observation", "code": {"text": "eGFR"}, "valueQuantity": quantity}


def test_relative_medication_references_resolve_within_the_requesting_server() -> None:
    patient = {"resourceType": "Patient", "id": "p1"}
    request = {
        "resourceType": "MedicationRequest",
        "status": "active",
        "subject": {"reference": "Patient/p1"},
        "medicationReference": {"reference": "Medication/m1"},
    }
    warfarin = _entry(
        {"resourceType": "Medication", "id": "m1", "code": {"text": "Warfarin 5 mg"}},
        "https://ehr-a.example/fhir/Medication/m1",
    )
    acetaminophen = _entry(
        {"resourceType": "Medication", "id": "m1", "code": {"text": "Acetaminophen"}},
        "https://ehr-b.example/fhir/Medication/m1",
    )
    request_a = _entry(request, "https://ehr-a.example/fhir/MedicationRequest/r1")

    same_server = _parse([_entry(patient), request_a, warfarin, acetaminophen])
    ambiguous = _parse([_entry(patient), _entry(request), warfarin, acetaminophen])
    other_server_only = _parse([_entry(patient), request_a, acetaminophen])

    assert [m["name"] for m in same_server["medications"]] == ["Warfarin 5 mg"]
    for result in (ambiguous, other_server_only):
        assert result["medications"] == []
        assert UNNAMED_ISSUE in result["screening_input_issues"]


def test_code_only_medications_are_reported_instead_of_screened_by_code() -> None:
    code_only = {
        "resourceType": "MedicationRequest",
        "status": "active",
        "medicationCodeableConcept": {"coding": [{"system": RXNORM, "code": "11289"}]},
    }
    display_in_second_coding = {
        "resourceType": "MedicationRequest",
        "status": "active",
        "medicationCodeableConcept": {
            "coding": [
                {"system": "urn:oid:2.16.840.1.113883.6.69", "code": "0093-0311"},
                {"system": RXNORM, "code": "6809", "display": "Metformin"},
            ]
        },
    }
    code_only_reference_with_display = {
        "resourceType": "MedicationRequest",
        "status": "active",
        "contained": [
            {
                "resourceType": "Medication",
                "id": "med",
                "code": {"coding": [{"system": RXNORM, "code": "1191"}]},
            }
        ],
        "medicationReference": {"reference": "#med", "display": "Aspirin"},
    }

    result = _parse(
        [
            _entry(PATIENT),
            _entry(code_only),
            _entry(display_in_second_coding),
            _entry(code_only_reference_with_display),
        ]
    )

    assert [m["name"] for m in result["medications"]] == ["Metformin", "Aspirin"]
    assert result["screening_input_issues"] == [UNNAMED_ISSUE]
    assert "11289" not in json.dumps(result["screening_input"])


def test_oversized_arrays_stop_validation_before_visiting_items() -> None:
    schema = TOOLS_BY_NAME["screen_medications"].input_schema

    errors = validate({"medications": [None] * 200_000}, schema)

    assert errors == ["arguments.medications must contain at most 100 items"]


def test_converted_egfr_keeps_its_measured_precision() -> None:
    near_threshold = _parse(
        [_entry(PATIENT), _entry(_egfr({"value": 30.04, "unit": "mL/min/1.73m2"}))]
    )
    converted = _parse([_entry(PATIENT), _entry(_egfr({"value": 0.35, "unit": "mL/s/1.73m2"}))])

    assert near_threshold["screening_input"]["patient"]["egfr"] == 30.04
    assert converted["screening_input"]["patient"]["egfr"] == 21.0


def test_patient_logical_id_is_redacted_from_clinical_text() -> None:
    patient = {"resourceType": "Patient", "id": "clinical-record-7f3"}
    condition = {
        "resourceType": "Condition",
        "subject": {"reference": "Patient/clinical-record-7f3"},
        "code": {"text": "AF documented for clinical-record-7f3"},
    }

    result = _parse([_entry(patient), _entry(condition)])

    assert "clinical-record-7f3" not in json.dumps(result)
    assert result["diagnoses"] == ["AF documented for [REDACTED-PATIENT]"]


def test_ucum_coded_egfr_quantities_drive_unit_conversion() -> None:
    code_without_unit = _egfr({"value": 28, "system": UCUM, "code": "mL/min/{1.73_m2}"})
    code_beats_free_text_unit = _egfr(
        {"value": 0.4, "unit": "mL/s per 1.73 m²", "system": UCUM, "code": "mL/s/{1.73_m2}"}
    )

    first = _parse([_entry(PATIENT), _entry(code_without_unit)])
    second = _parse([_entry(PATIENT), _entry(code_beats_free_text_unit)])

    assert first["screening_input"]["patient"]["egfr"] == 28
    assert second["screening_input"]["patient"]["egfr"] == 24.0


@pytest.mark.parametrize(
    "code",
    [
        {"coding": [{"system": LOINC, "code": "98979-8"}]},
        {
            "coding": [
                {"system": LOINC, "code": "98979-8", "display": "eGFRcr SerPlBld CKD-EPI 2021"}
            ]
        },
        {"coding": [{"system": LOINC, "code": "77147-7"}], "text": "GFR (MDRD)"},
    ],
    ids=["code-only", "loinc-short-name", "local-text"],
)
def test_loinc_coded_egfr_is_used_whatever_its_name(code: dict[str, Any]) -> None:
    observation = {
        "resourceType": "Observation",
        "code": code,
        "valueQuantity": {"value": 28, "unit": "mL/min/1.73m2"},
    }

    result = _parse([_entry(PATIENT), _entry(observation)])

    assert result["screening_input"]["patient"]["egfr"] == 28
    assert "egfr is the lowest of 1 eGFR observation(s)" in " ".join(result["notes"])


def test_only_loinc_egfr_codes_identify_an_unnamed_egfr() -> None:
    other_system = {"coding": [{"system": "urn:oid:2.16.840.1.113883.19", "code": "98979-8"}]}
    creatinine = {"coding": [{"system": LOINC, "code": "2160-0"}]}

    def observation(code: dict[str, Any]) -> dict[str, Any]:
        quantity = {"value": 28, "unit": "mL/min/1.73m2"}
        return _entry({"resourceType": "Observation", "code": code, "valueQuantity": quantity})

    result = _parse([_entry(PATIENT), observation(other_system), observation(creatinine)])

    assert "egfr" not in result["screening_input"]["patient"]


def test_malformed_medication_codings_are_tool_errors() -> None:
    request = {
        "resourceType": "MedicationRequest",
        "status": "active",
        "medicationCodeableConcept": {"coding": {"display": "Warfarin"}},
    }

    _rejects([_entry(PATIENT), _entry(request)], "unexpected structure")


# ---------------------------------------------------------------------------
# Final review pass
# ---------------------------------------------------------------------------


def _condition_on(server: str, condition_id: str, text: str) -> dict[str, Any]:
    condition = {
        "resourceType": "Condition",
        "id": condition_id,
        "subject": {"reference": "Patient/p1"},
        "code": {"text": text},
    }
    return _entry(condition, f"https://{server}.example/fhir/Condition/{condition_id}")


def test_relative_patient_references_resolve_on_their_own_server() -> None:
    patient_a = _entry(
        {"resourceType": "Patient", "id": "p1"}, "https://ehr-a.example/fhir/Patient/p1"
    )

    # "Patient/p1" in an ehr-b entry names ehr-b's patient p1, a different person.
    _rejects([patient_a, _condition_on("ehr-b", "c1", "CKD")], "mixes patients")
    _rejects(
        [_condition_on("ehr-a", "c1", "AF"), _condition_on("ehr-b", "c2", "CKD")],
        "mixes patients",
    )
    assert _parse([patient_a, _condition_on("ehr-a", "c1", "AF")])["diagnoses"] == ["AF"]
