"""Polypharmacy deprescribe suggester — HITL stop/step-down candidates (any age).

The existing :class:`~medagent.safety.geriatric_deprescribing_checker.GeriatricDeprescribingChecker`
applies an **age >= 65** curated deprescribing catalog (long-term PPI, Z-drugs,
first-generation antihistamines, chronic NSAIDs). It does not surface
cross-age polypharmacy reconciliation candidates such as duplicate-class
agents, high anticholinergic-burden contributors, sliding-scale insulin
stacking cues, or PPI-without-indication flags for younger adults.

This suggester fills that gap: deterministic token heuristics emit advisory
:class:`~medagent.models.PolypharmacyDeprescribeSuggestion` findings for
**human-in-the-loop** review. RESEARCH USE ONLY; never modifies medications;
never auto-stops therapy.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, PolypharmacyDeprescribeSuggestion, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_POLYPHARMACY_COUNT_MODERATE: Final[int] = 5
_POLYPHARMACY_COUNT_HIGH: Final[int] = 10
_HIGH_ACB_TOTAL: Final[int] = 3
_STRONG_ACB_SCORE: Final[int] = 3

_DUPLICATE_CLASSES: Final[tuple[tuple[str, frozenset[str]], ...]] = (
    (
        "ssri",
        frozenset(
            {
                "citalopram",
                "escitalopram",
                "fluoxetine",
                "fluvoxamine",
                "paroxetine",
                "sertraline",
            }
        ),
    ),
    (
        "snri",
        frozenset({"desvenlafaxine", "duloxetine", "levomilnacipran", "venlafaxine"}),
    ),
    (
        "benzodiazepine",
        frozenset(
            {
                "alprazolam",
                "chlordiazepoxide",
                "clonazepam",
                "diazepam",
                "lorazepam",
                "oxazepam",
                "temazepam",
            }
        ),
    ),
    (
        "ace_inhibitor",
        frozenset(
            {
                "benazepril",
                "captopril",
                "enalapril",
                "fosinopril",
                "lisinopril",
                "perindopril",
                "quinapril",
                "ramipril",
                "trandolapril",
            }
        ),
    ),
    (
        "arb",
        frozenset(
            {
                "azilsartan",
                "candesartan",
                "eprosartan",
                "irbesartan",
                "losartan",
                "olmesartan",
                "telmisartan",
                "valsartan",
            }
        ),
    ),
    (
        "statin",
        frozenset(
            {
                "atorvastatin",
                "fluvastatin",
                "lovastatin",
                "pitavastatin",
                "pravastatin",
                "rosuvastatin",
                "simvastatin",
            }
        ),
    ),
    (
        "nsaid",
        frozenset(
            {
                "celecoxib",
                "diclofenac",
                "ibuprofen",
                "indomethacin",
                "ketorolac",
                "meloxicam",
                "naproxen",
                "piroxicam",
            }
        ),
    ),
    (
        "opioid",
        frozenset(
            {
                "codeine",
                "fentanyl",
                "hydrocodone",
                "hydromorphone",
                "morphine",
                "oxycodone",
                "oxymorphone",
                "tramadol",
            }
        ),
    ),
    (
        "anticoagulant",
        frozenset(
            {
                "apixaban",
                "dabigatran",
                "edoxaban",
                "enoxaparin",
                "heparin",
                "rivaroxaban",
                "warfarin",
            }
        ),
    ),
    (
        "ppi",
        frozenset(
            {
                "dexlansoprazole",
                "esomeprazole",
                "lansoprazole",
                "omeprazole",
                "pantoprazole",
                "rabeprazole",
            }
        ),
    ),
)

_ACB_AGENTS: Final[dict[str, int]] = {
    "amitriptyline": 3,
    "atropine": 3,
    "benztropine": 3,
    "chlorpheniramine": 3,
    "chlorpromazine": 3,
    "clomipramine": 3,
    "clozapine": 3,
    "dicyclomine": 3,
    "diphenhydramine": 3,
    "doxepin": 3,
    "hydroxyzine": 3,
    "hyoscyamine": 3,
    "imipramine": 3,
    "meclizine": 3,
    "nortriptyline": 3,
    "olanzapine": 3,
    "oxybutynin": 3,
    "paroxetine": 3,
    "promethazine": 3,
    "quetiapine": 3,
    "scopolamine": 3,
    "solifenacin": 3,
    "tolterodine": 3,
    "amantadine": 2,
    "cimetidine": 2,
    "cyclobenzaprine": 2,
    "loxapine": 2,
    "alprazolam": 1,
    "haloperidol": 1,
    "loratadine": 1,
    "ranitidine": 1,
    "trazodone": 1,
}

_PPI_AGENTS: Final[frozenset[str]] = frozenset(
    {
        "dexlansoprazole",
        "esomeprazole",
        "lansoprazole",
        "omeprazole",
        "pantoprazole",
        "rabeprazole",
    }
)

_PPI_INDICATION_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "barrett",
        "barrett esophagus",
        "barrett oesophagus",
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

_SSI_PHRASES: Final[tuple[str, ...]] = (
    "sliding scale",
    "sliding-scale",
    "insulin sliding",
    "correction scale",
)

_INSULIN_AGENTS: Final[frozenset[str]] = frozenset(
    {
        "apidra",
        "aspart",
        "glulisine",
        "humalog",
        "humulin",
        "insulin",
        "lispro",
        "novolin",
        "novolog",
        "regular",
    }
)


class PolypharmacyDeprescribeSuggester:
    """Suggest HITL deprescribe candidates from polypharmacy heuristics (any age)."""

    def check(
        self,
        medications: list[Medication],
        indications: list[str] | None = None,
    ) -> list[PolypharmacyDeprescribeSuggestion]:
        """Return advisory deprescribe-candidate findings.

        Args:
            medications: Active patient medications (any age).
            indications: Optional free-text diagnoses / reasons for therapy.
                Used to suppress PPI-without-indication candidates when a
                protective GI indication is documented.

        Returns:
            Zero or more :class:`PolypharmacyDeprescribeSuggestion` findings.
            Distinct from age-gated :class:`GeriatricDeprescribingChecker`.
            Never modifies medications; never auto-stops therapy. Requires
            qualified clinician review before any medication change.
        """
        if not medications:
            logger.info("polypharmacy_deprescribe_checked", findings=0)
            return []

        indication_blob = self._indication_blob(indications or [])
        findings: list[PolypharmacyDeprescribeSuggestion] = []
        findings.extend(self._duplicate_class_candidates(medications))
        findings.extend(self._high_acb_candidates(medications))
        findings.extend(self._sliding_scale_insulin_candidates(medications))
        findings.extend(self._ppi_without_indication_candidates(medications, indication_blob))
        findings.extend(self._polypharmacy_count_candidates(medications))

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("polypharmacy_deprescribe_checked", findings=len(findings))
        return findings

    def _duplicate_class_candidates(
        self, medications: list[Medication]
    ) -> list[PolypharmacyDeprescribeSuggestion]:
        """Flag >=2 distinct agents in the same therapeutic class."""
        class_hits: dict[str, dict[str, str]] = {}
        for medication in medications:
            tokens = self._tokens(self._medication_text(medication))
            for class_name, agents in _DUPLICATE_CLASSES:
                for agent in sorted(tokens & agents):
                    class_hits.setdefault(class_name, {}).setdefault(agent, medication.name)

        findings: list[PolypharmacyDeprescribeSuggestion] = []
        for class_name, agent_map in sorted(class_hits.items()):
            if len(agent_map) < 2:
                continue
            agents = sorted(agent_map)
            med_names = sorted(set(agent_map.values()), key=str.casefold)
            findings.append(
                PolypharmacyDeprescribeSuggestion(
                    finding_kind="duplicate_therapy_deprescribe_candidate",
                    medication_names=med_names,
                    candidate_stops=agents,
                    severity=Severity.HIGH,
                    rationale=(
                        "RESEARCH USE ONLY: Duplicate-class polypharmacy deprescribe "
                        f"candidate — {len(agents)} distinct {class_name} agents "
                        f"({', '.join(agents)}) on the active list. HITL review may "
                        "consider supervised stop or consolidation of redundant "
                        "therapy. Distinct from age-gated GeriatricDeprescribingChecker. "
                        "Never auto-stops medications; requires human review. Prefer "
                        "GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                    ),
                )
            )
        return findings

    def _high_acb_candidates(
        self, medications: list[Medication]
    ) -> list[PolypharmacyDeprescribeSuggestion]:
        """Flag high cumulative ACB contributors as deprescribe candidates."""
        matched: dict[str, tuple[str, int]] = {}
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & set(_ACB_AGENTS)):
                matched.setdefault(agent, (medication.name, _ACB_AGENTS[agent]))

        if not matched:
            return []

        total = sum(score for _med, score in matched.values())
        if total < _HIGH_ACB_TOTAL:
            return []

        strong = sorted(
            agent for agent, (_med, score) in matched.items() if score >= _STRONG_ACB_SCORE
        )
        candidate_stops = strong or sorted(
            agent for agent, (_med, score) in matched.items() if score >= 2
        )
        if not candidate_stops:
            candidate_stops = sorted(matched)

        med_names = sorted({med for med, _score in matched.values()}, key=str.casefold)
        severity = Severity.CRITICAL if total >= 5 or len(strong) >= 2 else Severity.HIGH
        return [
            PolypharmacyDeprescribeSuggestion(
                finding_kind="high_burden_deprescribe_candidate",
                medication_names=med_names,
                candidate_stops=candidate_stops,
                severity=severity,
                rationale=(
                    "RESEARCH USE ONLY: High anticholinergic-burden deprescribe "
                    f"candidate — cumulative ACB {total} across "
                    f"{', '.join(sorted(matched))}. HITL candidate stops: "
                    f"{', '.join(candidate_stops)}. Distinct from age-gated "
                    "GeriatricDeprescribingChecker and from per-medication "
                    "AnticholinergicBurdenChecker. Never auto-stops medications; "
                    "requires human review. Prefer GPT-5.5 / Claude Sonnet 4.6 / "
                    "Gemini 3.x / Kimi K2."
                ),
            )
        ]

    def _sliding_scale_insulin_candidates(
        self, medications: list[Medication]
    ) -> list[PolypharmacyDeprescribeSuggestion]:
        """Flag sliding-scale insulin stacking cues as deprescribe candidates."""
        hits: list[tuple[str, str]] = []
        for medication in medications:
            text = self._medication_text(medication)
            tokens = self._tokens(text)
            insulin_hit = sorted(tokens & _INSULIN_AGENTS)
            if not insulin_hit:
                continue
            if not self._has_sliding_scale_cue(tokens, text):
                continue
            hits.append((medication.name, insulin_hit[0]))

        if not hits:
            return []

        med_names = sorted({name for name, _agent in hits}, key=str.casefold)
        agents = sorted({agent for _name, agent in hits})
        severity = Severity.HIGH if len(hits) >= 2 else Severity.MODERATE
        return [
            PolypharmacyDeprescribeSuggestion(
                finding_kind="sliding_scale_insulin_deprescribe_candidate",
                medication_names=med_names,
                candidate_stops=agents,
                severity=severity,
                rationale=(
                    "RESEARCH USE ONLY: Sliding-scale insulin deprescribe candidate — "
                    f"SSI/stacking cues on {', '.join(med_names)}. HITL review may "
                    "consider transitioning away from sliding-scale-only coverage. "
                    "Distinct from InsulinStackingChecker bolus-timing checks and "
                    "age-gated GeriatricDeprescribingChecker. Never auto-stops "
                    "medications; requires human review. Prefer GPT-5.5 / Claude "
                    "Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )
        ]

    def _ppi_without_indication_candidates(
        self,
        medications: list[Medication],
        indication_blob: str,
    ) -> list[PolypharmacyDeprescribeSuggestion]:
        """Flag PPI therapy without a documented protective indication."""
        if self._aliases_match(indication_blob, _PPI_INDICATION_ALIASES):
            return []

        hits: dict[str, str] = {}
        for medication in medications:
            tokens = self._tokens(self._medication_text(medication))
            for agent in sorted(tokens & _PPI_AGENTS):
                hits.setdefault(agent, medication.name)

        if not hits:
            return []

        agents = sorted(hits)
        med_names = sorted(set(hits.values()), key=str.casefold)
        return [
            PolypharmacyDeprescribeSuggestion(
                finding_kind="ppi_without_indication_deprescribe_candidate",
                medication_names=med_names,
                candidate_stops=agents,
                severity=Severity.LOW,
                rationale=(
                    "RESEARCH USE ONLY: PPI-without-indication deprescribe candidate — "
                    f"{', '.join(agents)} without a documented protective GI "
                    "indication. HITL review may consider step-down or supervised "
                    "stop. Applies at any age (not age-gated); distinct from "
                    "GeriatricDeprescribingChecker age>=65 catalog. Never auto-stops "
                    "medications; requires human review. Prefer GPT-5.5 / Claude "
                    "Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )
        ]

    def _polypharmacy_count_candidates(
        self, medications: list[Medication]
    ) -> list[PolypharmacyDeprescribeSuggestion]:
        """Flag elevated medication counts as reconciliation candidates."""
        count = len(medications)
        if count < _POLYPHARMACY_COUNT_MODERATE:
            return []

        med_names = sorted({med.name for med in medications}, key=str.casefold)
        severity = Severity.HIGH if count >= _POLYPHARMACY_COUNT_HIGH else Severity.MODERATE
        return [
            PolypharmacyDeprescribeSuggestion(
                finding_kind="polypharmacy_count_candidate",
                medication_names=med_names,
                candidate_stops=[],
                severity=severity,
                rationale=(
                    "RESEARCH USE ONLY: Polypharmacy count deprescribe candidate — "
                    f"{count} active medications (threshold "
                    f">={_POLYPHARMACY_COUNT_MODERATE}). HITL medication "
                    "reconciliation may identify supervised stop or step-down "
                    "opportunities. Distinct from age-gated "
                    "GeriatricDeprescribingChecker. Never auto-stops medications; "
                    "requires human review. Prefer GPT-5.5 / Claude Sonnet 4.6 / "
                    "Gemini 3.x / Kimi K2."
                ),
            )
        ]

    @staticmethod
    def _medication_text(medication: Medication) -> str:
        """Return searchable medication text including dose/frequency metadata."""
        return " ".join(
            value
            for value in (
                medication.name,
                medication.dosage,
                medication.frequency,
                medication.route,
            )
            if value
        )

    @staticmethod
    def _tokens(text: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    @staticmethod
    def _indication_blob(indications: list[str]) -> str:
        """Join free-text indications into a lowercase searchable blob."""
        return " ".join(indications).lower()

    @staticmethod
    def _has_sliding_scale_cue(tokens: set[str], text: str) -> bool:
        """Return True when medication text suggests sliding-scale insulin."""
        if "ssi" in tokens or "sliding" in tokens:
            return True
        normalized = text.lower().replace("-", " ")
        return any(phrase.replace("-", " ") in normalized for phrase in _SSI_PHRASES)

    @staticmethod
    def _aliases_match(blob: str, aliases: frozenset[str]) -> bool:
        """Return True when any alias matches as a whole token or phrase."""
        if not blob or not aliases:
            return False
        tokens = set(re.findall(r"[a-z0-9]+", blob))
        for alias in aliases:
            alias_l = alias.lower()
            if " " in alias_l or "-" in alias_l:
                if alias_l in blob:
                    return True
                continue
            if alias_l in tokens:
                return True
        return False
