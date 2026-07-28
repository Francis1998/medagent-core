"""Taper-schedule advisory safety checker.

Taper planning is different from automatically stopping or prescribing a
medication. Chronic exposure to opioids, benzodiazepines/Z-drugs, proton-pump
inhibitors, and SSRIs/SNRIs can make abrupt discontinuation unsafe or poorly
tolerated. This checker therefore emits structured, research-only advisory
``TaperScheduleRisk`` records that prompt clinician review; it never generates a
patient-specific taper schedule and never modifies a medication list.

Medication matching is deterministic and whole-token based (never loose
substrings). The curated panel is intentionally conservative and requires
scheduled/chronic-use cues before a medication is flagged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, Severity, TaperScheduleRisk

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_LONG_TERM_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "bid",
        "chronic",
        "daily",
        "maintenance",
        "nightly",
        "patch",
        "qday",
        "qd",
        "qid",
        "scheduled",
        "tid",
    }
)

_LONG_TERM_PHRASES: Final[tuple[str, ...]] = (
    "around the clock",
    "every day",
    "extended release",
    "four times daily",
    "long term",
    "long-term",
    "once daily",
    "sustained release",
    "three times daily",
    "twice daily",
)

_PPI_INDICATION_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "barrett",
        "barrett esophagus",
        "barrett oesophagus",
        "chronic nsaid gastroprotection",
        "erosive esophagitis",
        "erosive oesophagitis",
        "gastroprotection",
        "gi bleed",
        "gi bleeding",
        "gib",
        "peptic ulcer",
        "severe gerd",
        "upper gi bleed",
        "zollinger ellison",
    }
)


@dataclass(frozen=True)
class _TaperRule:
    """A curated taper-schedule advisory panel entry."""

    agent: str
    aliases: frozenset[str]
    medication_class: str
    taper_opportunity: str
    suggested_review: str
    abrupt_stop_concern: str
    severity: Severity
    suppress_with_indication_aliases: frozenset[str] = frozenset()


_OPIOID_REVIEW = (
    "verify ongoing indication, duration, function goals, and withdrawal/overdose risk; "
    "if deprescribing is appropriate, a qualified clinician should design an "
    "individualized gradual taper"
)
_BENZODIAZEPINE_Z_REVIEW = (
    "review anxiety/insomnia indication, falls/cognition risk, and dependence risk; "
    "if discontinuation is appropriate, use clinician-supervised gradual taper planning"
)
_PPI_REVIEW = (
    "confirm ongoing acid-suppression indication; if no high-risk indication remains, "
    "consider clinician-supervised step-down, dose reduction, or taper review"
)
_SSRI_SNRI_REVIEW = (
    "review symptom stability, relapse risk, and discontinuation-syndrome risk; "
    "if stopping is appropriate, use clinician-supervised gradual taper planning"
)

_TAPER_RULES: Final[tuple[_TaperRule, ...]] = (
    _TaperRule(
        "morphine",
        frozenset({"morphine", "mscontin"}),
        "opioid",
        "chronic opioid taper-schedule review",
        _OPIOID_REVIEW,
        "abrupt opioid discontinuation can precipitate withdrawal, pain destabilization, "
        "psychological distress, or unsafe non-prescribed opioid use",
        Severity.HIGH,
    ),
    _TaperRule(
        "oxycodone",
        frozenset({"oxycontin", "oxycodone", "percocet", "roxicodone"}),
        "opioid",
        "chronic opioid taper-schedule review",
        _OPIOID_REVIEW,
        "abrupt opioid discontinuation can precipitate withdrawal, pain destabilization, "
        "psychological distress, or unsafe non-prescribed opioid use",
        Severity.HIGH,
    ),
    _TaperRule(
        "hydrocodone",
        frozenset({"hydrocodone", "norco", "vicodin"}),
        "opioid",
        "chronic opioid taper-schedule review",
        _OPIOID_REVIEW,
        "abrupt opioid discontinuation can precipitate withdrawal, pain destabilization, "
        "psychological distress, or unsafe non-prescribed opioid use",
        Severity.HIGH,
    ),
    _TaperRule(
        "hydromorphone",
        frozenset({"dilaudid", "hydromorphone"}),
        "opioid",
        "chronic opioid taper-schedule review",
        _OPIOID_REVIEW,
        "abrupt opioid discontinuation can precipitate withdrawal, pain destabilization, "
        "psychological distress, or unsafe non-prescribed opioid use",
        Severity.HIGH,
    ),
    _TaperRule(
        "methadone",
        frozenset({"dolophine", "methadone"}),
        "opioid",
        "chronic opioid taper-schedule review",
        _OPIOID_REVIEW,
        "abrupt methadone discontinuation can cause prolonged opioid withdrawal and "
        "destabilize pain or opioid-use-disorder treatment",
        Severity.HIGH,
    ),
    _TaperRule(
        "fentanyl",
        frozenset({"duragesic", "fentanyl"}),
        "opioid",
        "chronic opioid taper-schedule review",
        _OPIOID_REVIEW,
        "abrupt fentanyl discontinuation can precipitate opioid withdrawal and pain "
        "destabilization",
        Severity.HIGH,
    ),
    _TaperRule(
        "tramadol",
        frozenset({"tramadol", "ultram"}),
        "opioid",
        "chronic opioid taper-schedule review",
        _OPIOID_REVIEW,
        "abrupt tramadol discontinuation can cause opioid withdrawal and serotonergic "
        "discontinuation symptoms",
        Severity.HIGH,
    ),
    _TaperRule(
        "alprazolam",
        frozenset({"alprazolam", "xanax"}),
        "benzodiazepine_z_drug",
        "benzodiazepine/Z-drug taper-schedule review",
        _BENZODIAZEPINE_Z_REVIEW,
        "abrupt benzodiazepine discontinuation can precipitate withdrawal, rebound "
        "anxiety/insomnia, seizures, or delirium",
        Severity.HIGH,
    ),
    _TaperRule(
        "clonazepam",
        frozenset({"clonazepam", "klonopin"}),
        "benzodiazepine_z_drug",
        "benzodiazepine/Z-drug taper-schedule review",
        _BENZODIAZEPINE_Z_REVIEW,
        "abrupt benzodiazepine discontinuation can precipitate withdrawal, rebound "
        "anxiety/insomnia, seizures, or delirium",
        Severity.HIGH,
    ),
    _TaperRule(
        "diazepam",
        frozenset({"diazepam", "valium"}),
        "benzodiazepine_z_drug",
        "benzodiazepine/Z-drug taper-schedule review",
        _BENZODIAZEPINE_Z_REVIEW,
        "abrupt benzodiazepine discontinuation can precipitate withdrawal, rebound "
        "anxiety/insomnia, seizures, or delirium",
        Severity.HIGH,
    ),
    _TaperRule(
        "lorazepam",
        frozenset({"ativan", "lorazepam"}),
        "benzodiazepine_z_drug",
        "benzodiazepine/Z-drug taper-schedule review",
        _BENZODIAZEPINE_Z_REVIEW,
        "abrupt benzodiazepine discontinuation can precipitate withdrawal, rebound "
        "anxiety/insomnia, seizures, or delirium",
        Severity.HIGH,
    ),
    _TaperRule(
        "temazepam",
        frozenset({"restoril", "temazepam"}),
        "benzodiazepine_z_drug",
        "benzodiazepine/Z-drug taper-schedule review",
        _BENZODIAZEPINE_Z_REVIEW,
        "abrupt benzodiazepine discontinuation can precipitate withdrawal, rebound "
        "insomnia, seizures, or delirium",
        Severity.HIGH,
    ),
    _TaperRule(
        "zolpidem",
        frozenset({"ambien", "zolpidem"}),
        "benzodiazepine_z_drug",
        "benzodiazepine/Z-drug taper-schedule review",
        _BENZODIAZEPINE_Z_REVIEW,
        "abrupt Z-drug discontinuation can cause rebound insomnia and withdrawal symptoms",
        Severity.HIGH,
    ),
    _TaperRule(
        "eszopiclone",
        frozenset({"eszopiclone", "lunesta"}),
        "benzodiazepine_z_drug",
        "benzodiazepine/Z-drug taper-schedule review",
        _BENZODIAZEPINE_Z_REVIEW,
        "abrupt Z-drug discontinuation can cause rebound insomnia and withdrawal symptoms",
        Severity.HIGH,
    ),
    _TaperRule(
        "zaleplon",
        frozenset({"sonata", "zaleplon"}),
        "benzodiazepine_z_drug",
        "benzodiazepine/Z-drug taper-schedule review",
        _BENZODIAZEPINE_Z_REVIEW,
        "abrupt Z-drug discontinuation can cause rebound insomnia and withdrawal symptoms",
        Severity.HIGH,
    ),
    _TaperRule(
        "omeprazole",
        frozenset({"omeprazole", "prilosec"}),
        "ppi",
        "long-term PPI step-down/taper review",
        _PPI_REVIEW,
        "abrupt PPI discontinuation can cause rebound acid hypersecretion and symptom relapse",
        Severity.LOW,
        _PPI_INDICATION_ALIASES,
    ),
    _TaperRule(
        "pantoprazole",
        frozenset({"pantoprazole", "protonix"}),
        "ppi",
        "long-term PPI step-down/taper review",
        _PPI_REVIEW,
        "abrupt PPI discontinuation can cause rebound acid hypersecretion and symptom relapse",
        Severity.LOW,
        _PPI_INDICATION_ALIASES,
    ),
    _TaperRule(
        "esomeprazole",
        frozenset({"esomeprazole", "nexium"}),
        "ppi",
        "long-term PPI step-down/taper review",
        _PPI_REVIEW,
        "abrupt PPI discontinuation can cause rebound acid hypersecretion and symptom relapse",
        Severity.LOW,
        _PPI_INDICATION_ALIASES,
    ),
    _TaperRule(
        "lansoprazole",
        frozenset({"lansoprazole", "prevacid"}),
        "ppi",
        "long-term PPI step-down/taper review",
        _PPI_REVIEW,
        "abrupt PPI discontinuation can cause rebound acid hypersecretion and symptom relapse",
        Severity.LOW,
        _PPI_INDICATION_ALIASES,
    ),
    _TaperRule(
        "sertraline",
        frozenset({"sertraline", "zoloft"}),
        "ssri",
        "SSRI discontinuation taper review",
        _SSRI_SNRI_REVIEW,
        "abrupt SSRI discontinuation can cause discontinuation symptoms and symptom relapse",
        Severity.MODERATE,
    ),
    _TaperRule(
        "fluoxetine",
        frozenset({"fluoxetine", "prozac"}),
        "ssri",
        "SSRI discontinuation taper review",
        _SSRI_SNRI_REVIEW,
        "abrupt SSRI discontinuation can cause discontinuation symptoms and symptom relapse",
        Severity.MODERATE,
    ),
    _TaperRule(
        "paroxetine",
        frozenset({"paroxetine", "paxil"}),
        "ssri",
        "SSRI discontinuation taper review",
        _SSRI_SNRI_REVIEW,
        "abrupt paroxetine discontinuation can cause prominent discontinuation symptoms "
        "and symptom relapse",
        Severity.MODERATE,
    ),
    _TaperRule(
        "citalopram",
        frozenset({"celexa", "citalopram"}),
        "ssri",
        "SSRI discontinuation taper review",
        _SSRI_SNRI_REVIEW,
        "abrupt SSRI discontinuation can cause discontinuation symptoms and symptom relapse",
        Severity.MODERATE,
    ),
    _TaperRule(
        "escitalopram",
        frozenset({"escitalopram", "lexapro"}),
        "ssri",
        "SSRI discontinuation taper review",
        _SSRI_SNRI_REVIEW,
        "abrupt SSRI discontinuation can cause discontinuation symptoms and symptom relapse",
        Severity.MODERATE,
    ),
    _TaperRule(
        "venlafaxine",
        frozenset({"effexor", "venlafaxine"}),
        "snri",
        "SNRI discontinuation taper review",
        _SSRI_SNRI_REVIEW,
        "abrupt venlafaxine discontinuation can cause prominent discontinuation symptoms "
        "and symptom relapse",
        Severity.MODERATE,
    ),
    _TaperRule(
        "desvenlafaxine",
        frozenset({"desvenlafaxine", "pristiq"}),
        "snri",
        "SNRI discontinuation taper review",
        _SSRI_SNRI_REVIEW,
        "abrupt SNRI discontinuation can cause discontinuation symptoms and symptom relapse",
        Severity.MODERATE,
    ),
    _TaperRule(
        "duloxetine",
        frozenset({"cymbalta", "duloxetine"}),
        "snri",
        "SNRI discontinuation taper review",
        _SSRI_SNRI_REVIEW,
        "abrupt SNRI discontinuation can cause discontinuation symptoms and symptom relapse",
        Severity.MODERATE,
    ),
)


class TaperScheduleChecker:
    """Flag conservative research-only taper-schedule review opportunities."""

    def check(
        self,
        medications: list[Medication],
        indications: list[str] | None = None,
        clinical_notes: str | None = None,
    ) -> list[TaperScheduleRisk]:
        """Return taper-schedule advisory findings.

        Args:
            medications: Active patient medications.
            indications: Optional free-text diagnoses / reasons for therapy.
                PPI findings are suppressed when protective high-risk GI
                indications are documented.
            clinical_notes: Optional free-text notes included in indication
                context for PPI suppression.

        Returns:
            One :class:`TaperScheduleRisk` per matching chronic/scheduled
            medication, ordered by descending severity then class/agent/name.
            Findings are advisory and do not provide patient-specific taper
            instructions.
        """
        indication_blob = self._context_blob(indications or [], clinical_notes)
        findings: list[TaperScheduleRisk] = []
        for medication in medications:
            medication_text = self._medication_text(medication)
            tokens = self._tokens(medication_text)
            if not tokens or not self._has_long_term_signal(tokens, medication_text):
                continue
            for rule in self._matching_rules(tokens, indication_blob):
                findings.append(
                    TaperScheduleRisk(
                        medication=medication.name,
                        agent=rule.agent,
                        medication_class=rule.medication_class,
                        taper_opportunity=rule.taper_opportunity,
                        suggested_review=rule.suggested_review,
                        abrupt_stop_concern=rule.abrupt_stop_concern,
                        taper_candidate=True,
                        severity=rule.severity,
                        rationale=(
                            "RESEARCH USE ONLY: "
                            f"Medication '{medication.name}' contains {rule.agent}, which "
                            f"matches the taper advisory category '{rule.taper_opportunity}'. "
                            f"Concern: {rule.abrupt_stop_concern}. Suggested review: "
                            f"{rule.suggested_review}. This finding does not prescribe, stop, "
                            "or auto-generate a taper schedule; any medication change requires "
                            "qualified clinician assessment and individualized planning."
                        ),
                    )
                )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.medication_class,
                finding.agent,
                finding.medication.lower(),
            )
        )
        logger.info("taper_schedule_checked", findings=len(findings))
        return findings

    def _matching_rules(
        self,
        tokens: set[str],
        indication_blob: str,
    ) -> list[_TaperRule]:
        """Return taper rules matched by medication tokens after indication gates."""
        matched_rules: list[_TaperRule] = []
        matched_agents: set[str] = set()
        for rule in _TAPER_RULES:
            if rule.agent in matched_agents:
                continue
            if not (tokens & rule.aliases):
                continue
            if rule.suppress_with_indication_aliases and self._aliases_match(
                indication_blob,
                rule.suppress_with_indication_aliases,
            ):
                continue
            matched_agents.add(rule.agent)
            matched_rules.append(rule)
        matched_rules.sort(
            key=lambda rule: (-_SEVERITY_RANK[rule.severity], rule.medication_class, rule.agent)
        )
        return matched_rules

    @staticmethod
    def _medication_text(medication: Medication) -> str:
        """Return searchable medication text including dose/frequency metadata."""
        return " ".join(
            medication_part
            for medication_part in (
                medication.name,
                medication.dosage,
                medication.frequency,
                medication.route,
            )
            if medication_part
        )

    @staticmethod
    def _tokens(text: str) -> set[str]:
        """Return lowercase alphanumeric component tokens from free text."""
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    @staticmethod
    def _has_long_term_signal(tokens: set[str], text: str) -> bool:
        """Return True when medication text suggests chronic or scheduled use."""
        if tokens & _LONG_TERM_TOKENS:
            return True
        normalized_text = text.lower().replace("-", " ")
        return any(phrase.replace("-", " ") in normalized_text for phrase in _LONG_TERM_PHRASES)

    @staticmethod
    def _context_blob(indications: list[str], clinical_notes: str | None) -> str:
        """Join indication strings and optional clinical notes into normalized text."""
        context_parts = [indication for indication in indications if indication.strip()]
        if clinical_notes and clinical_notes.strip():
            context_parts.append(clinical_notes)
        return " ".join(context_parts).strip().lower()

    @classmethod
    def _aliases_match(cls, blob: str, aliases: frozenset[str]) -> bool:
        """Return True when any alias matches as a whole token or phrase."""
        if not blob or not aliases:
            return False
        normalized_blob = cls._normalise_text(blob)
        blob_tokens = set(normalized_blob.split())
        padded_blob = f" {normalized_blob} "
        for alias in aliases:
            normalized_alias = cls._normalise_text(alias)
            if " " in normalized_alias:
                if f" {normalized_alias} " in padded_blob:
                    return True
                continue
            if normalized_alias in blob_tokens:
                return True
        return False

    @staticmethod
    def _normalise_text(text: str) -> str:
        """Normalize text to lowercase alphanumeric tokens separated by spaces."""
        return " ".join(re.findall(r"[a-z0-9]+", text.lower()))
