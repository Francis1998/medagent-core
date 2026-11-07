"""Unit tests for the CDS Hooks engine: FHIR → deterministic screen → cards (no HTTP)."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

from medagent.agent.audit import CDS_HOOKS_AUDIT_COLUMNS
from medagent.cds_hooks import SERVICES_BY_ID, CdsHooksRequestError, engine, evaluate_hook
from medagent.cds_hooks.engine import INDICATOR_BY_SEVERITY, SUMMARY_MAX_CHARS
from medagent.cds_hooks.services import (
    OVERRIDE_REASON_SYSTEM,
    PREFETCH_TEMPLATES,
    SOURCE_LABEL,
)
from medagent.safety.disclaimer import MANDATORY_DISCLAIMER
from medagent.safety.pii_hasher import hash_pii

EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "cds_hooks"
ORDER_SIGN = SERVICES_BY_ID["medagent-medication-safety"]
ORDER_SELECT = SERVICES_BY_ID["medagent-medication-safety-select"]
PATIENT_ID = "cds-demo-ada"


def example(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def order_sign(*drafts: dict[str, Any], prefetch: Any = "example") -> dict[str, Any]:
    """The order-sign example with its draft orders replaced (and optionally its prefetch)."""
    body = example("order-sign.json")
    if drafts:
        body["context"]["draftOrders"]["entry"] = [{"resource": draft} for draft in drafts]
    if prefetch != "example":
        if prefetch is None:
            del body["prefetch"]
        else:
            body["prefetch"] = prefetch
    return body


def draft(name: str | None, resource_id: str = "draft-1", **fields: Any) -> dict[str, Any]:
    resource: dict[str, Any] = {
        "resourceType": "MedicationRequest",
        "id": resource_id,
        "status": "draft",
        "intent": "order",
        "subject": {"reference": f"Patient/{PATIENT_ID}"},
    }
    if name is not None:
        resource["medicationCodeableConcept"] = {"text": name}
    resource.update(fields)
    return resource


def searchset(*resources: dict[str, Any], **fields: Any) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [{"resource": resource} for resource in resources],
        **fields,
    }


def summaries(cards: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(card["indicator"], card["summary"]) for card in cards]


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------


def test_order_sign_example_flags_the_cross_order_interaction_as_critical() -> None:
    result = evaluate_hook(ORDER_SIGN, example("order-sign.json"))

    assert summaries(result.cards) == [
        (
            "critical",
            "Critical — Drug-drug interaction: Warfarin sodium 5 mg tablet + "
            "Fluconazole 150 mg tablet",
        ),
        ("warning", "Moderate — Additive QT-prolongation burden: Fluconazole 150 mg tablet"),
    ]
    card = result.cards[0]
    assert MANDATORY_DISCLAIMER in card["detail"]
    assert "`warfarin_azole` (WarfarinAzoleChecker) · severity **CRITICAL**" in card["detail"]
    assert (
        "Warfarin sodium 5 mg tablet (current medication); "
        "Fluconazole 150 mg tablet (draft order)" in card["detail"]
    )
    assert "Escalation recommended" in card["detail"]
    assert card["source"]["label"] == SOURCE_LABEL == "medagent-core (research use only)"
    assert card["source"]["topic"]["code"] == "interaction"
    assert {reason["system"] for reason in card["overrideReasons"]} == {OVERRIDE_REASON_SYSTEM}
    assert all(reason["display"] for reason in card["overrideReasons"])
    for card in result.cards:
        assert len(card["summary"]) < 140
        assert "suggestions" not in card
        assert "selectionBehavior" not in card
        assert card["links"][0]["type"] == "absolute"
    assert result.prefetch_gaps == ()
    assert result.finding_count == 2


def test_findings_about_current_medications_alone_are_not_carded() -> None:
    """Metformin at eGFR 28 and warfarin's boxed warning concern current therapy only."""
    result = evaluate_hook(ORDER_SIGN, example("order-sign.json"))

    text = json.dumps(result.cards)
    assert "Metformin" not in text
    assert "black_box_warning" not in text
    assert "renal_dose" not in text


def test_severity_to_indicator_mapping_is_the_documented_table() -> None:
    assert INDICATOR_BY_SEVERITY == {
        "CRITICAL": "critical",
        "HIGH": "warning",
        "MODERATE": "warning",
        "LOW": "info",
        "UNKNOWN": "warning",
    }


def test_benign_orders_return_no_cards() -> None:
    result = evaluate_hook(ORDER_SIGN, order_sign(draft("Acetaminophen 500 mg tablet")))

    assert result.cards == []
    assert result.finding_count == 0
    call = result.audit_events[0]
    assert call["event"] == "service_call"
    assert call["card_count"] == 0
    assert call["indicator"] is None


def test_findings_involving_one_ordered_medication_are_grouped_into_one_card() -> None:
    result = evaluate_hook(ORDER_SIGN, order_sign(draft("Ibuprofen 400 mg tablet")))

    assert summaries(result.cards) == [
        ("warning", "High — Renal dosing against eGFR: Ibuprofen 400 mg tablet (2 checks)"),
        (
            "warning",
            "High — Drug-drug interaction: Warfarin sodium 5 mg tablet + Ibuprofen 400 mg tablet "
            "(2 checks)",
        ),
    ]
    renal = result.cards[0]["detail"]
    assert "`renal_dose`" in renal and "`black_box_warning`" in renal
    interaction = result.cards[1]["detail"]
    assert "`warfarin_nsaid`" in interaction and "`anticoag_bleeding`" in interaction
    assert result.finding_count == 4


def test_card_order_is_deterministic_and_uuids_are_unique() -> None:
    first = evaluate_hook(ORDER_SIGN, order_sign(draft("Ibuprofen 400 mg tablet")))
    second = evaluate_hook(ORDER_SIGN, order_sign(draft("Ibuprofen 400 mg tablet")))

    assert summaries(first.cards) == summaries(second.cards)
    assert [card["detail"] for card in first.cards] == [card["detail"] for card in second.cards]
    uuids = [card["uuid"] for card in first.cards + second.cards]
    assert len(set(uuids)) == len(uuids)


# ---------------------------------------------------------------------------
# Prefetch
# ---------------------------------------------------------------------------


def test_without_prefetch_only_the_draft_orders_are_screened_and_an_info_card_says_so() -> None:
    result = evaluate_hook(ORDER_SIGN, order_sign(prefetch=None))

    assert summaries(result.cards) == [
        ("warning", "Moderate — Additive QT-prolongation burden: Fluconazole 150 mg tablet"),
        (
            "info",
            "Partial medication-safety screen: missing prefetch patient, activeMedications, "
            "allergies, egfr",
        ),
    ]
    coverage = result.cards[-1]
    assert MANDATORY_DISCLAIMER in coverage["detail"]
    for key in PREFETCH_TEMPLATES:
        assert f"Prefetch `{key}` was not provided" in coverage["detail"]
    assert "never queries the FHIR server" in coverage["detail"]
    assert coverage["source"]["topic"]["code"] == "screen_coverage"
    assert "overrideReasons" not in coverage
    assert result.prefetch_gaps == tuple(PREFETCH_TEMPLATES)


def test_partial_prefetch_names_only_the_missing_keys() -> None:
    body = order_sign()
    del body["prefetch"]["egfr"]

    result = evaluate_hook(ORDER_SIGN, body)

    assert result.cards[0]["indicator"] == "critical"
    assert result.cards[-1]["summary"] == "Partial medication-safety screen: missing prefetch egfr"
    assert "renal dosing was not checked" in result.cards[-1]["detail"]
    assert result.prefetch_gaps == ("egfr",)


def test_null_prefetch_means_no_data_rather_than_missing_data() -> None:
    body = order_sign(draft("Amoxicillin 500 mg capsule"))
    for key in ("activeMedications", "allergies", "egfr"):
        body["prefetch"][key] = None

    result = evaluate_hook(ORDER_SIGN, body)

    assert result.cards == []
    assert result.prefetch_gaps == ()


def test_allergy_checks_use_prefetched_allergies() -> None:
    result = evaluate_hook(ORDER_SIGN, order_sign(draft("Amoxicillin 500 mg capsule")))

    assert summaries(result.cards) == [
        (
            "warning",
            "High — Drug-allergy conflicts (direct and intra-class): Amoxicillin 500 mg capsule",
        )
    ]


def test_prefetch_operation_outcomes_and_pagination_are_reported() -> None:
    body = order_sign()
    body["prefetch"]["activeMedications"] = {
        "resourceType": "OperationOutcome",
        "issue": [{"severity": "error", "code": "timeout"}],
    }
    body["prefetch"]["egfr"] = searchset(
        link=[{"relation": "next", "url": "https://ehr.example.org/fhir?page=2"}]
    )

    result = evaluate_hook(ORDER_SIGN, body)

    coverage = result.cards[-1]
    assert coverage["indicator"] == "info"
    assert coverage["summary"] == (
        "Partial medication-safety screen: incomplete prefetch activeMedications, egfr"
    )
    assert "Prefetch `activeMedications` held an error (OperationOutcome)" in coverage["detail"]
    assert "Prefetch `egfr` was paginated" in coverage["detail"]
    assert "warfarin_azole" not in json.dumps(result.cards)


def test_prefetched_operation_outcome_entries_mark_the_key_but_keep_its_resources() -> None:
    body = order_sign()
    body["prefetch"]["activeMedications"]["entry"].append(
        {
            "resource": {
                "resourceType": "OperationOutcome",
                "issue": [{"severity": "error", "code": "too-costly"}],
            },
            "search": {"mode": "outcome"},
        }
    )

    result = evaluate_hook(ORDER_SIGN, body)

    assert result.cards[0]["indicator"] == "critical"
    assert result.prefetch_gaps == ("activeMedications",)


def test_a_current_order_revised_in_this_session_is_screened_once_as_a_draft() -> None:
    body = order_sign()
    revised = copy.deepcopy(body["prefetch"]["activeMedications"]["entry"][0]["resource"])
    body["context"]["draftOrders"]["entry"].append({"resource": revised})

    result = evaluate_hook(ORDER_SIGN, body)

    assert (
        "**Medications involved:** Warfarin sodium 5 mg tablet (draft order); "
        "Fluconazole 150 mg tablet (draft order)" in result.cards[0]["detail"]
    )


# ---------------------------------------------------------------------------
# order-select
# ---------------------------------------------------------------------------


def test_order_select_reports_only_findings_that_involve_a_selected_order() -> None:
    result = evaluate_hook(ORDER_SELECT, example("order-select.json"))

    assert summaries(result.cards) == [
        (
            "warning",
            "High — Drug-allergy conflicts (direct and intra-class): Amoxicillin 500 mg capsule",
        )
    ]
    assert "Amoxicillin 500 mg capsule (selected order)" in result.cards[0]["detail"]

    body = example("order-select.json")
    body["context"]["selections"] = ["MedicationRequest/draft-fluconazole"]
    result = evaluate_hook(ORDER_SELECT, body)

    assert result.cards[0]["indicator"] == "critical"
    assert "Fluconazole 150 mg tablet (selected order)" in result.cards[0]["detail"]
    assert "Amoxicillin" not in json.dumps(result.cards)


def test_order_select_selections_must_reference_draft_orders() -> None:
    body = example("order-select.json")
    body["context"]["selections"] = ["MedicationRequest/not-in-the-bundle"]

    with pytest.raises(CdsHooksRequestError) as raised:
        evaluate_hook(ORDER_SELECT, body)

    assert raised.value.reason == "unknown_selection"
    assert "not-in-the-bundle" not in raised.value.message


def test_selecting_only_non_medication_orders_returns_no_cards() -> None:
    body = example("order-select.json")
    lab = {"resourceType": "ServiceRequest", "id": "lab-1", "status": "draft", "intent": "order"}
    body["context"]["draftOrders"]["entry"].append({"resource": lab})
    body["context"]["selections"] = ["ServiceRequest/lab-1"]

    assert evaluate_hook(ORDER_SELECT, body).cards == []


# ---------------------------------------------------------------------------
# Patient binding and FHIR edge cases
# ---------------------------------------------------------------------------


def _other_patient_draft(body: dict[str, Any]) -> None:
    body["context"]["draftOrders"]["entry"][0]["resource"]["subject"] = {
        "reference": "Patient/CANARY-other-patient"
    }


def _other_patient_prefetch(body: dict[str, Any]) -> None:
    body["prefetch"]["patient"]["id"] = "CANARY-other-patient"


def _other_patient_allergy(body: dict[str, Any]) -> None:
    resource = body["prefetch"]["allergies"]["entry"][0]["resource"]
    resource["patient"] = {"reference": "https://ehr.example.org/fhir/Patient/CANARY-other-patient"}


def _identifier_only_subject(body: dict[str, Any]) -> None:
    body["prefetch"]["egfr"]["entry"][0]["resource"]["subject"] = {
        "identifier": {"system": "https://ehr.example.org/mrn", "value": "CANARY-other-patient"}
    }


@pytest.mark.parametrize(
    "mutate",
    [
        _other_patient_draft,
        _other_patient_prefetch,
        _other_patient_allergy,
        _identifier_only_subject,
    ],
)
def test_resources_for_another_patient_are_rejected(mutate: Any) -> None:
    body = example("order-sign.json")
    mutate(body)

    with pytest.raises(CdsHooksRequestError) as raised:
        evaluate_hook(ORDER_SIGN, body)

    assert raised.value.reason == "patient_mismatch"
    assert "CANARY" not in raised.value.message


def test_absolute_and_versioned_patient_references_are_accepted() -> None:
    body = example("order-sign.json")
    body["context"]["draftOrders"]["entry"][0]["resource"]["subject"] = {
        "reference": f"https://ehr.example.org/fhir/Patient/{PATIENT_ID}/_history/3"
    }

    assert evaluate_hook(ORDER_SIGN, body).cards[0]["indicator"] == "critical"


def test_unnamed_draft_orders_are_reported_not_screened_by_code() -> None:
    code_only = draft(
        None,
        "draft-code-only",
        medicationCodeableConcept={
            "coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "197699"}]
        },
    )
    fluconazole = example("order-sign.json")["context"]["draftOrders"]["entry"][0]["resource"]

    result = evaluate_hook(ORDER_SIGN, order_sign(fluconazole, code_only))

    assert result.cards[0]["indicator"] == "critical"
    assert result.cards[-1]["summary"] == (
        "Partial medication-safety screen: 1 medication(s) not screened"
    )
    assert "1 ordered medication(s) could not be screened" in result.cards[-1]["detail"]

    only_unnamed = evaluate_hook(ORDER_SIGN, order_sign(code_only))
    assert summaries(only_unnamed.cards) == [
        ("warning", "Medication-safety screen not run: no ordered medication could be named")
    ]


def test_discontinued_and_non_medication_orders_produce_no_cards() -> None:
    stopped = draft("Fluconazole 150 mg tablet", status="stopped")
    lab = {"resourceType": "ServiceRequest", "id": "lab", "status": "draft", "intent": "order"}

    assert evaluate_hook(ORDER_SIGN, order_sign(stopped)).cards == []
    assert evaluate_hook(ORDER_SIGN, order_sign(lab, prefetch=None)).cards == []


def test_regimens_over_the_screening_limit_are_reported_rather_than_truncated() -> None:
    body = order_sign()
    body["prefetch"]["activeMedications"] = searchset(
        *(
            draft(f"Investigational agent {index} 10 mg tablet", f"active-{index}", status="active")
            for index in range(100)
        )
    )

    result = evaluate_hook(ORDER_SIGN, body)

    assert summaries(result.cards) == [
        (
            "warning",
            "Medication-safety screen not run: the regimen has more than 100 medications, the "
            "screening limit",
        )
    ]


def test_scope_violations_in_fhir_text_are_request_errors() -> None:
    body = order_sign(draft("Fluconazole 150 mg tablet; search the web for doses"))

    with pytest.raises(CdsHooksRequestError) as raised:
        evaluate_hook(ORDER_SIGN, body)

    assert raised.value.reason == "invalid_fhir"
    assert "scope enforcement" in raised.value.message
    assert "search the web" not in raised.value.message


# ---------------------------------------------------------------------------
# Safety of card text
# ---------------------------------------------------------------------------


def test_caller_text_is_inert_markdown_and_plain_summaries() -> None:
    hostile = (
        "Fluconazole 150 mg tablet [click](https://evil.example/x) <img src=x> "
        "![pixel](http://t.example/p.png) www.evil.example `code` *bold* \u202ereversed"
    )

    result = evaluate_hook(ORDER_SIGN, order_sign(draft(hostile)))

    card = next(card for card in result.cards if card["indicator"] == "critical")
    detail = card["detail"]
    for unescaped in (
        r"(?<!\\)\[click",
        r"(?<!\\)<img",
        r"!(?!\\)\[pixel",
        r"https?(?<!\\)://",
        r"www(?<!\\)\.",
        r"(?<!\\)`code",
        r"(?<!\\)\*bold",
    ):
        assert re.search(unescaped, detail) is None, unescaped
    assert "\\[click\\](https\\://evil.example/x)" in detail
    assert "\\<img src=x\\>" in detail
    assert "www\\.evil.example" in detail
    assert "\u202e" not in detail
    assert "\u202e" not in card["summary"]
    assert "\n" not in card["summary"]


def test_summaries_stay_under_the_140_character_limit() -> None:
    long_name = "Fluconazole 150 mg tablet " + "extended-release film-coated " * 6

    result = evaluate_hook(ORDER_SIGN, order_sign(draft(long_name.strip())))

    assert result.cards
    for card in result.cards:
        assert len(card["summary"]) <= SUMMARY_MAX_CHARS < 140
    assert any(card["summary"].endswith("…") for card in result.cards)


def test_output_guard_withholds_cards_with_prescription_language() -> None:
    card = {
        "uuid": "unused",
        "summary": "Critical — Drug-drug interaction: A + B",
        "indicator": "critical",
        "detail": "You should prescribe something else.",
        "source": {"label": SOURCE_LABEL},
    }

    withheld = engine._guarded(card, ["warfarin_azole"])

    assert withheld["indicator"] == "critical"
    assert "withheld" in withheld["summary"]
    assert "`warfarin_azole`" in withheld["detail"]
    assert "prescribe something" not in json.dumps(withheld)
    assert MANDATORY_DISCLAIMER in withheld["detail"]


def test_every_real_card_passes_the_output_guard() -> None:
    for body in (
        example("order-sign.json"),
        order_sign(prefetch=None),
        order_sign(draft("Ibuprofen 400 mg tablet")),
    ):
        for card in evaluate_hook(ORDER_SIGN, body).cards:
            assert "withheld" not in card["summary"]


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------


def test_audit_events_hold_hashes_ids_and_codes_only() -> None:
    body = example("order-sign.json")
    result = evaluate_hook(ORDER_SIGN, body)

    call, *cards = result.audit_events
    assert call == {
        "event": "service_call",
        "service_id": "medagent-medication-safety",
        "hook": "order-sign",
        "hook_instance_hash": hash_pii(body["hookInstance"]),
        "patient_id_hash": hash_pii(PATIENT_ID),
        "user_id_hash": hash_pii("Practitioner/demo-prescriber"),
        "card_count": 2,
        "finding_count": 2,
        "indicator": "critical",
        "check_ids": "qt_prolongation,warfarin_azole",
        "prefetch_gaps": None,
    }
    assert [event["card_uuid"] for event in cards] == [card["uuid"] for card in result.cards]
    assert [event["check_ids"] for event in cards] == ["warfarin_azole", "qt_prolongation"]
    for event in result.audit_events:
        assert set(event) <= set(CDS_HOOKS_AUDIT_COLUMNS)
    serialized = json.dumps(result.audit_events)
    for raw in (PATIENT_ID, "demo-prescriber", body["hookInstance"], "Fluconazole", "Penicillin"):
        assert raw not in serialized


# ---------------------------------------------------------------------------
# Prefetch shapes and FHIR edge cases
# ---------------------------------------------------------------------------


def test_a_prefetched_single_resource_is_used_like_a_one_entry_bundle() -> None:
    body = order_sign()
    body["prefetch"]["activeMedications"] = body["prefetch"]["activeMedications"]["entry"][0][
        "resource"
    ]

    result = evaluate_hook(ORDER_SIGN, body)

    assert result.cards[0]["indicator"] == "critical"
    assert result.prefetch_gaps == ()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("patient", {"resourceType": "Practitioner", "id": "x"}),
        ("patient", ["not", "an", "object"]),
        ("egfr", {"resourceType": "Bundle", "entry": "not-a-list"}),
        ("allergies", {"resourceType": "Bundle", "entry": ["not-an-entry"]}),
        ("activeMedications", {"resourceType": "Condition", "id": "c1"}),
    ],
)
def test_unusable_prefetch_values_are_reported_as_errors(key: str, value: Any) -> None:
    body = order_sign()
    body["prefetch"][key] = value

    result = evaluate_hook(ORDER_SIGN, body)

    assert result.prefetch_gaps == (key,)
    assert f"Prefetch `{key}` held an error" in result.cards[-1]["detail"]


def test_oversized_prefetch_bundles_are_rejected() -> None:
    body = order_sign()
    body["prefetch"]["allergies"]["entry"] = [{}] * 5001

    with pytest.raises(CdsHooksRequestError) as raised:
        evaluate_hook(ORDER_SIGN, body)

    assert raised.value.reason == "too_many_entries"


def test_included_medication_resources_name_referenced_current_orders() -> None:
    body = order_sign()
    warfarin = body["prefetch"]["activeMedications"]["entry"][0]["resource"]
    del warfarin["medicationCodeableConcept"]
    warfarin["medicationReference"] = {"reference": "Medication/med-warfarin"}
    body["prefetch"]["activeMedications"]["entry"].append(
        {
            "fullUrl": "https://ehr.example.org/fhir/Medication/med-warfarin",
            "resource": {
                "resourceType": "Medication",
                "id": "med-warfarin",
                "code": {"text": "Warfarin sodium 5 mg tablet"},
            },
            "search": {"mode": "include"},
        }
    )

    result = evaluate_hook(ORDER_SIGN, body)

    assert result.cards[0]["indicator"] == "critical"
    assert "Warfarin sodium 5 mg tablet (current medication)" in result.cards[0]["detail"]


def test_unnamed_current_medications_are_reported() -> None:
    body = order_sign()
    body["prefetch"]["activeMedications"]["entry"].append(
        {"resource": draft(None, "active-unnamed", status="active")}
    )

    result = evaluate_hook(ORDER_SIGN, body)

    assert result.cards[-1]["summary"] == (
        "Partial medication-safety screen: 1 medication(s) not screened"
    )
    assert (
        "1 other medication(s) (unsigned or current) could not be screened"
        in (result.cards[-1]["detail"])
    )


def test_selections_may_name_a_draft_order_by_full_url() -> None:
    body = example("order-select.json")
    url = "urn:uuid:5b7c9d1e-2f3a-4b5c-8d6e-7f8a9b0c1d2e"
    body["context"]["draftOrders"]["entry"][1]["fullUrl"] = url
    body["context"]["selections"] = [url]

    result = evaluate_hook(ORDER_SELECT, body)

    assert "Amoxicillin 500 mg capsule (selected order)" in result.cards[0]["detail"]


def test_malformed_fhir_structures_are_request_errors() -> None:
    body = order_sign()
    body["prefetch"]["patient"]["name"] = [{"given": 5}]

    with pytest.raises(CdsHooksRequestError) as raised:
        evaluate_hook(ORDER_SIGN, body)

    assert raised.value.reason == "invalid_fhir"
    assert raised.value.message == (
        "FHIR data could not be parsed: a resource has an unexpected structure (TypeError)."
    )


def test_text_beyond_the_screening_limits_falls_back_to_the_medication_name() -> None:
    fluconazole = draft(
        "Fluconazole 150 mg tablet", dosageInstruction=[{"text": "one tablet " * 40}]
    )

    result = evaluate_hook(ORDER_SIGN, order_sign(fluconazole))

    assert result.cards[0]["indicator"] == "critical"
    assert all(card["source"]["topic"]["code"] != "screen_coverage" for card in result.cards)


def test_patient_context_outside_the_screening_limits_is_not_used() -> None:
    body = order_sign()
    egfr = body["prefetch"]["egfr"]["entry"][0]["resource"]
    egfr["valueQuantity"]["value"] = 300

    result = evaluate_hook(ORDER_SIGN, body)

    assert result.cards[0]["indicator"] == "critical"
    assert result.cards[-1]["summary"] == "Partial medication-safety screen: unusable egfr"
    assert "`egfr` was outside the screening limits" in result.cards[-1]["detail"]


def test_coverage_card_lists_status_exclusions_but_not_included_drafts() -> None:
    fluconazole = example("order-sign.json")["context"]["draftOrders"]["entry"][0]["resource"]
    cancelled = draft("Ibuprofen 400 mg tablet", "draft-cancelled", status="cancelled")

    result = evaluate_hook(ORDER_SIGN, order_sign(fluconazole, cancelled, prefetch=None))

    detail = result.cards[-1]["detail"]
    assert (
        "- Not screened because of order status: excluded MedicationRequest status cancelled: 1."
        in detail
    )
    assert "include" not in detail.replace("including", "")
    assert "Ibuprofen" not in json.dumps(result.cards)
