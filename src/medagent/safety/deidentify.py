"""De-identify an analysis request before retrieval or any LLM call (SAFETY.md §3.5).

The agent applies :func:`deidentify_query` at INTAKE, so every later stage —
entity extraction, PubMed/RxNorm/OpenFDA retrieval, the LLM prompt, the result
and the audit record — only ever sees the de-identified copy.
"""

from __future__ import annotations

import re

from medagent.extraction.fhir_parser import sanitise_clinical_text
from medagent.models import ClinicalQuery, FHIRPatientContext
from medagent.safety.pii_hasher import hash_pii, redact_fhir_pii

_HEX_DIGEST = re.compile(r"[0-9a-fA-F]{64}")


def deidentify_patient_context(context: FHIRPatientContext) -> FHIRPatientContext:
    """Return a copy of ``context`` with identifiers removed from its narrative fields.

    Args:
        context: Patient context as supplied by the caller.

    Returns:
        A copy in which the chief complaint, clinical notes, diagnoses and
        allergies have passed through :func:`sanitise_clinical_text`, a
        ``patient_id_hash`` that is not already a 64-character hex digest is
        HMAC-SHA256 hashed, and ``raw_fhir`` has its Patient name, birth date,
        identifiers, telecom and address removed. Structured medication, lab
        and vital-sign records are clinical content and are kept unchanged.
    """
    patient_id = context.patient_id_hash
    if not _HEX_DIGEST.fullmatch(patient_id):
        patient_id = hash_pii(patient_id)
    raw_fhir = redact_fhir_pii(context.raw_fhir) if context.raw_fhir is not None else None
    return context.model_copy(
        update={
            "patient_id_hash": patient_id,
            "chief_complaint": sanitise_clinical_text(context.chief_complaint),
            "clinical_notes": sanitise_clinical_text(context.clinical_notes),
            "diagnoses_history": [sanitise_clinical_text(d) for d in context.diagnoses_history],
            "allergies": [sanitise_clinical_text(a) for a in context.allergies],
            "raw_fhir": raw_fhir,
        }
    )


def deidentify_query(query: ClinicalQuery) -> ClinicalQuery:
    """Return a copy of ``query`` with its question and patient context de-identified.

    Args:
        query: Clinical query as received by the agent.

    Returns:
        A copy with the same session id whose ``query`` text has passed
        through :func:`sanitise_clinical_text` and whose patient context has
        been de-identified by :func:`deidentify_patient_context`.
    """
    return query.model_copy(
        update={
            "patient_context": deidentify_patient_context(query.patient_context),
            "query": sanitise_clinical_text(query.query),
        }
    )
