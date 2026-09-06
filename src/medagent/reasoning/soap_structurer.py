"""Deterministic SOAP note structurer.

Builds Subjective / Objective / Assessment / Plan sections from clinical notes,
extracted entities, lab results, and medications using transparent heuristics.

Plan text is limited to non-prescriptive hints (review/consider/follow-up cues).
This module never emits prescriptions, doses, or refill instructions.

RESEARCH USE ONLY — educational documentation structuring, distinct from
MedPrompt-style LLM SOAP generation.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import ClinicalEntity, LabResult, Medication, SoapNote

logger = get_logger(__name__)

_SUBJECTIVE_HINTS: Final[tuple[str, ...]] = (
    "reports",
    "complains",
    "complaint",
    "history of present",
    "hpi",
    "states",
    "denies",
    "endorses",
    "pain",
    "symptom",
    "feels",
    "felt",
    "subjective",
)

_OBJECTIVE_HINTS: Final[tuple[str, ...]] = (
    "exam",
    "vital",
    "spo2",
    "blood pressure",
    "heart rate",
    "temperature",
    "labs",
    "laboratory",
    "imaging",
    "ct ",
    "mri",
    "x-ray",
    "ultrasound",
    "objective",
    "on exam",
    "auscultation",
    "abdomen",
    "lungs",
)

_ASSESSMENT_HINTS: Final[tuple[str, ...]] = (
    "assessment",
    "impression",
    "diagnosis",
    "differential",
    "likely",
    "consistent with",
    "suspect",
    "working diagnosis",
)

_PLAN_HINTS: Final[tuple[str, ...]] = (
    "plan",
    "follow-up",
    "follow up",
    "monitor",
    "recheck",
    "discuss",
    "consider",
    "return precautions",
)

_DISEASE_LABELS: Final[set[str]] = {
    "disease",
    "disorder",
    "finding",
    "symptom",
    "problem",
    "condition",
    "diagnosis",
}

_EMPTY: Final[str] = "(none documented)"


def _split_sentences(text: str) -> list[str]:
    """Split free text into lightweight sentence-like chunks."""
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _matches_any(text: str, hints: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in hints)


class SoapStructurer:
    """Deterministically structure clinical inputs into SOAP sections."""

    def structure(
        self,
        clinical_note: str = "",
        entities: list[ClinicalEntity] | None = None,
        lab_results: list[LabResult] | None = None,
        medications: list[Medication] | None = None,
        chief_complaint: str | None = None,
    ) -> SoapNote:
        """Return a SoapNote assembled with transparent heuristics.

        Args:
            clinical_note: Free-text clinician note.
            entities: Optional extracted clinical entities.
            lab_results: Optional laboratory results.
            medications: Optional active medications (used only for plan hints).
            chief_complaint: Optional presenting complaint.

        Returns:
            A :class:`SoapNote` with S/O/A/P sections. Plan contains
            non-prescriptive hints only. Always RESEARCH USE ONLY.
        """
        entities = entities or []
        lab_results = lab_results or []
        medications = medications or []

        sentences = _split_sentences(clinical_note)
        subjective_bits: list[str] = []
        objective_bits: list[str] = []
        assessment_bits: list[str] = []
        plan_bits: list[str] = []

        if chief_complaint and chief_complaint.strip():
            subjective_bits.append(f"Chief complaint: {chief_complaint.strip()}")

        for sentence in sentences:
            if _matches_any(sentence, _PLAN_HINTS) and not _matches_any(
                sentence, _ASSESSMENT_HINTS
            ):
                plan_bits.append(self._as_hint(sentence))
            elif _matches_any(sentence, _ASSESSMENT_HINTS):
                assessment_bits.append(sentence)
            elif _matches_any(sentence, _OBJECTIVE_HINTS):
                objective_bits.append(sentence)
            elif _matches_any(sentence, _SUBJECTIVE_HINTS):
                subjective_bits.append(sentence)
            else:
                # Default residual narrative to subjective for documentation continuity.
                subjective_bits.append(sentence)

        for entity in entities:
            label = (entity.label or "").strip().lower()
            text = entity.text.strip()
            if not text:
                continue
            if label in _DISEASE_LABELS or "disease" in label or "symptom" in label:
                assessment_bits.append(f"Entity ({entity.label}): {text}")
                if "symptom" in label:
                    subjective_bits.append(f"Reported symptom entity: {text}")
            elif "lab" in label or "test" in label:
                objective_bits.append(f"Entity ({entity.label}): {text}")

        for lab in lab_results:
            flag = " abnormal" if lab.abnormal else ""
            unit = f" {lab.unit}" if lab.unit else ""
            objective_bits.append(f"Lab: {lab.test_name}={lab.value}{unit}{flag}".strip())

        # Plan hints from medications/labs — never prescribe.
        for medication in medications:
            plan_bits.append(
                f"Consider clinician review of active medication '{medication.name}' "
                "(no medication-order instruction issued)."
            )
        for lab in lab_results:
            if lab.abnormal:
                plan_bits.append(
                    f"Consider clinician follow-up regarding abnormal lab '{lab.test_name}' "
                    "(monitoring hint only)."
                )

        if not plan_bits:
            plan_bits.append(
                "Consider clinician follow-up and documentation review "
                "(non-prescriptive hint only)."
            )

        note = SoapNote(
            subjective=self._join(subjective_bits),
            objective=self._join(objective_bits),
            assessment=self._join(assessment_bits),
            plan=self._join(self._dedupe(plan_bits)),
            rationale=(
                "RESEARCH USE ONLY: Deterministic SOAP structuring from notes, "
                "entities, labs, and medications using keyword/section heuristics. "
                "Plan contains non-prescriptive hints only and never issues "
                "prescriptions or doses. Distinct from MedPrompt-style LLM SOAP "
                "generation. Prefer frontier summarization with GPT-5.5 / "
                "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
            ),
        )
        logger.info(
            "soap_structured",
            subjective_len=len(note.subjective),
            objective_len=len(note.objective),
            assessment_len=len(note.assessment),
            plan_len=len(note.plan),
        )
        return note

    @staticmethod
    def _join(parts: list[str]) -> str:
        cleaned = [part.strip() for part in parts if part and part.strip()]
        return " ".join(cleaned) if cleaned else _EMPTY

    @staticmethod
    def _dedupe(parts: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for part in parts:
            key = part.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(part.strip())
        return ordered

    @staticmethod
    def _as_hint(sentence: str) -> str:
        """Rewrite plan-like sentences into explicitly non-prescriptive hints."""
        text = sentence.strip()
        lowered = text.lower()
        banned = ("prescribe", "start ", "increase dose", "decrease dose", "dispense")
        if any(token in lowered for token in banned):
            return (
                "Plan cue redacted into non-prescriptive hint: consider clinician "
                "review of documented plan language (no medication order issued)."
            )
        if not lowered.startswith("consider"):
            return f"Consider clinician review: {text}"
        return text
