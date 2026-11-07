"""Tool-level tests for the medagent MCP server: semantics, schemas and safety."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from medagent.mcp.schema import validate
from medagent.mcp.tools import (
    TOOLS,
    TOOLS_BY_NAME,
    ToolInputError,
    ToolOutput,
    interaction_checks,
    safety_control_catalog,
)
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
        ({"medications": ["x"], "extra": 1}, "arguments.extra is not an allowed property"),
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
    assert "[REDACTED-PHONE]" in result["chief_complaint"]
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
    assert "lowest of 2 numeric eGFR" in " ".join(result["notes"])

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
