"""FHIR MedicationRequest adapter for safety-panel Medication lists.

The existing :mod:`medagent.extraction.fhir_parser` parses full FHIR Bundles
(Patient, Condition, MedicationRequest, Observation, AllergyIntolerance) into
:class:`~medagent.models.FHIRPatientContext`. Safety panels typically need only
a thin ``MedicationRequest`` → :class:`~medagent.models.Medication` mapping
without re-running the full bundle parser.

This adapter accepts MedicationRequest-like dicts (or a list/Bundle wrapper),
emits a :class:`~medagent.models.FhirMedicationParseResult` with medications
plus rationale notes, and is RESEARCH USE ONLY.
"""

from __future__ import annotations

from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import FhirMedicationParseResult, Medication, Severity

logger = get_logger(__name__)

_ACTIVE_STATUSES: Final[frozenset[str]] = frozenset(
    {"active", "completed", "on-hold", "draft", "unknown", ""}
)


class FhirMedicationRequestAdapter:
    """Map FHIR MedicationRequest-like dicts to Medication lists for safety panels."""

    def adapt(
        self,
        payload: dict[str, Any] | list[Any] | None,
    ) -> FhirMedicationParseResult:
        """Adapt MedicationRequest-like input into medications + rationale notes.

        Args:
            payload: A single MedicationRequest dict, a list of such dicts, a
                Bundle-like dict with ``entry`` resources, or None.

        Returns:
            :class:`FhirMedicationParseResult` with parsed medications, skip
            notes, severity (informational), and RESEARCH USE ONLY rationale.
            Distinct from :func:`medagent.extraction.fhir_parser.parse_fhir_bundle`.
        """
        notes: list[str] = []
        resources = self._normalize_resources(payload, notes)
        medications: list[Medication] = []
        skipped = 0

        for index, resource in enumerate(resources):
            if not isinstance(resource, dict):
                skipped += 1
                notes.append(f"entry[{index}]: skipped non-object resource")
                continue
            resource_type = str(resource.get("resourceType") or "MedicationRequest")
            if resource_type not in {"MedicationRequest", "MedicationStatement", ""}:
                # Allow missing resourceType for thin MedicationRequest-like dicts.
                has_med = (
                    "medicationCodeableConcept" in resource or "medicationReference" in resource
                )
                if not has_med:
                    skipped += 1
                    notes.append(
                        f"entry[{index}]: skipped resourceType '{resource_type}' "
                        "(expected MedicationRequest-like)"
                    )
                    continue

            status = str(resource.get("status") or "").lower()
            if status and status not in _ACTIVE_STATUSES and status == "cancelled":
                skipped += 1
                notes.append(f"entry[{index}]: skipped cancelled MedicationRequest")
                continue
            if status == "stopped":
                skipped += 1
                notes.append(f"entry[{index}]: skipped stopped MedicationRequest")
                continue
            if status == "entered-in-error":
                skipped += 1
                notes.append(f"entry[{index}]: skipped entered-in-error MedicationRequest")
                continue

            name, rxnorm, name_note = self._extract_name(resource)
            if name_note:
                notes.append(f"entry[{index}]: {name_note}")
            if not name:
                skipped += 1
                notes.append(f"entry[{index}]: skipped - no medication name/display")
                continue

            dosage, route, frequency = self._extract_dosage(resource)
            medications.append(
                Medication(
                    name=name,
                    rxnorm_code=rxnorm,
                    dosage=dosage,
                    route=route,
                    frequency=frequency,
                )
            )

        severity = Severity.LOW if medications else Severity.UNKNOWN
        rationale = (
            "RESEARCH USE ONLY: FhirMedicationRequestAdapter mapped "
            f"{len(medications)} MedicationRequest-like resource(s) into "
            f"Medication objects for safety-panel use "
            f"(skipped={skipped}). Thin adapter distinct from "
            "extraction.fhir_parser full-bundle parsing. Not a clinical "
            "order. Prefer frontier summarization with GPT-5.5 / "
            "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
        )
        if notes:
            rationale += " Notes: " + "; ".join(notes[:12])
            if len(notes) > 12:
                rationale += f"; …and {len(notes) - 12} more"

        result = FhirMedicationParseResult(
            medications=medications,
            resource_count=len(resources),
            skipped_count=skipped,
            notes=notes,
            severity=severity,
            rationale=rationale,
        )
        logger.info(
            "fhir_medication_request_adapted",
            medications=len(medications),
            skipped=skipped,
            resources=len(resources),
        )
        return result

    def check(
        self,
        payload: dict[str, Any] | list[Any] | None,
    ) -> list[FhirMedicationParseResult]:
        """Duck-typed safety entrypoint returning a one-element result list."""
        return [self.adapt(payload)]

    @staticmethod
    def _normalize_resources(
        payload: dict[str, Any] | list[Any] | None,
        notes: list[str],
    ) -> list[Any]:
        """Normalize payload into a flat list of resource dicts."""
        if payload is None:
            notes.append("payload was None - no resources")
            return []
        if isinstance(payload, list):
            return list(payload)
        if not isinstance(payload, dict):
            notes.append("payload was not a dict or list")
            return []
        if payload.get("resourceType") == "Bundle":
            entries = payload.get("entry") or []
            resources: list[Any] = []
            for entry in entries:
                if isinstance(entry, dict) and "resource" in entry:
                    resources.append(entry["resource"])
                elif isinstance(entry, dict):
                    resources.append(entry)
            return resources
        if payload.get("resourceType") == "MedicationRequest" or (
            "medicationCodeableConcept" in payload or "medicationReference" in payload
        ):
            return [payload]
        # Dict keyed by resource type, e.g. {"MedicationRequest": [...]}
        if "MedicationRequest" in payload and isinstance(payload["MedicationRequest"], list):
            return list(payload["MedicationRequest"])
        notes.append("unrecognized payload shape - treating as empty")
        return []

    @staticmethod
    def _extract_name(resource: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
        """Return (name, rxnorm, note) from medicationCodeableConcept / Reference."""
        med_code = resource.get("medicationCodeableConcept") or {}
        name = med_code.get("text") if isinstance(med_code, dict) else None
        rxnorm = None
        note = None
        if isinstance(med_code, dict):
            codings = med_code.get("coding") or []
            if not name and codings:
                name = codings[0].get("display") or codings[0].get("code")
            for coding in codings:
                system = str(coding.get("system") or "").lower()
                if system.endswith("rxnorm") or "rxnorm" in system:
                    rxnorm = coding.get("code")
                    break
        if not name:
            ref = resource.get("medicationReference") or {}
            if isinstance(ref, dict):
                name = ref.get("display")
                if name:
                    note = "name taken from medicationReference.display"
        return name, rxnorm, note

    @staticmethod
    def _extract_dosage(
        resource: dict[str, Any],
    ) -> tuple[str | None, str | None, str | None]:
        """Return (dosage_text, route, frequency) from dosageInstruction."""
        dosage_instructions = resource.get("dosageInstruction") or []
        if not dosage_instructions or not isinstance(dosage_instructions, list):
            return None, None, None
        di = dosage_instructions[0] if isinstance(dosage_instructions[0], dict) else {}
        dosage_text = di.get("text")
        route_text = None
        route = di.get("route") or {}
        if isinstance(route, dict):
            route_text = route.get("text")
            if not route_text:
                route_coding = route.get("coding") or []
                if route_coding and isinstance(route_coding[0], dict):
                    route_text = route_coding[0].get("display")
        timing_text = None
        timing = di.get("timing") or {}
        if isinstance(timing, dict):
            code = timing.get("code") or {}
            if isinstance(code, dict):
                timing_text = code.get("text")
            if not timing_text and "repeat" in timing:
                repeat = timing["repeat"] or {}
                freq = repeat.get("frequency")
                period = repeat.get("period")
                unit = repeat.get("periodUnit")
                if freq is not None:
                    timing_text = f"{freq} per {period or 1} {unit or 'd'}"
        return dosage_text, route_text, timing_text
