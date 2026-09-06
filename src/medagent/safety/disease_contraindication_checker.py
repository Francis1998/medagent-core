"""Disease × medication contraindication panel checker.

Flags well-known condition–drug educational contraindications using
whole-token matching, for example heart failure with NSAIDs or asthma with
nonselective beta-blockers. This is distinct from pairwise drug–drug
interaction checkers.

Findings are advisory RESEARCH USE ONLY records and never modify medications.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import DiseaseContraindicationRisk, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical condition key -> acceptable whole-token phrases (lowercase tokens joined).
# Multi-word conditions are matched when all tokens appear as whole tokens in order
# or as a contiguous phrase in the tokenized condition string.
_CONDITION_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "heart_failure": (
        "heart failure",
        "congestive heart failure",
        "chf",
        "hfref",
        "hfpef",
        "cardiac failure",
    ),
    "asthma": ("asthma", "bronchial asthma"),
    "parkinson_disease": (
        "parkinson disease",
        "parkinsons disease",
        "parkinson",
        "parkinsons",
    ),
    "gout": ("gout", "gouty arthritis"),
    "myasthenia_gravis": ("myasthenia gravis", "myasthenia"),
    "ckd": (
        "ckd",
        "chronic kidney disease",
        "chronic renal failure",
        "renal failure",
    ),
}

# panel_id -> (condition_key, agents, severity, concern)
_PANELS: Final[dict[str, tuple[str, frozenset[str], Severity, str]]] = {
    "hf_nsaid": (
        "heart_failure",
        frozenset(
            {
                "ibuprofen",
                "naproxen",
                "diclofenac",
                "ketorolac",
                "meloxicam",
                "indomethacin",
                "celecoxib",
                "piroxicam",
            }
        ),
        Severity.HIGH,
        "NSAID use in heart failure may worsen fluid retention and heart-failure status",
    ),
    "asthma_nonselective_bb": (
        "asthma",
        frozenset(
            {
                "propranolol",
                "nadolol",
                "timolol",
                "sotalol",
                "pindolol",
                "carvedilol",
            }
        ),
        Severity.HIGH,
        "nonselective beta-blockade may precipitate bronchospasm in asthma",
    ),
    "parkinson_dopamine_blockers": (
        "parkinson_disease",
        frozenset(
            {
                "metoclopramide",
                "prochlorperazine",
                "promethazine",
                "haloperidol",
            }
        ),
        Severity.HIGH,
        "dopamine-blocking antiemetics/antipsychotics may worsen Parkinsonism",
    ),
    "gout_thiazide": (
        "gout",
        frozenset({"hydrochlorothiazide", "hctz", "chlorthalidone", "indapamide"}),
        Severity.MODERATE,
        "thiazide diuretics may raise uric acid and precipitate gout flares",
    ),
    "mg_aminoglycoside": (
        "myasthenia_gravis",
        frozenset({"gentamicin", "tobramycin", "amikacin", "streptomycin"}),
        Severity.HIGH,
        "aminoglycosides may worsen neuromuscular blockade in myasthenia gravis",
    ),
    "ckd_nsaid": (
        "ckd",
        frozenset(
            {
                "ibuprofen",
                "naproxen",
                "diclofenac",
                "ketorolac",
                "meloxicam",
                "indomethacin",
                "celecoxib",
            }
        ),
        Severity.HIGH,
        "NSAID use in CKD may reduce renal perfusion and worsen kidney function",
    ),
}


class DiseaseContraindicationChecker:
    """Flag curated disease × medication educational contraindications."""

    def check(
        self,
        conditions: list[str],
        medications: list[Medication],
    ) -> list[DiseaseContraindicationRisk]:
        """Return advisory findings for matching condition × drug panels.

        Args:
            conditions: Patient condition/diagnosis strings.
            medications: Active medications.

        Returns:
            One :class:`DiseaseContraindicationRisk` per unique
            (panel_id, condition_string, medication_name, agent) match,
            ordered by descending severity then panel id and names.
            Matching uses whole-token logic for both conditions and drugs.
        """
        matched_conditions: list[tuple[str, str]] = []
        for condition in conditions:
            for condition_key in _CONDITION_ALIASES:
                if self._condition_match(condition, condition_key):
                    matched_conditions.append((condition, condition_key))

        if not matched_conditions:
            logger.info("disease_contraindication_checked", findings=0)
            return []

        findings: list[DiseaseContraindicationRisk] = []
        seen: set[tuple[str, str, str, str]] = set()

        for medication in medications:
            agents = sorted(self._tokens(medication.name) & self._all_agents())
            if not agents:
                continue
            for agent in agents:
                for condition, condition_key in matched_conditions:
                    for panel_id, (
                        panel_condition,
                        panel_agents,
                        severity,
                        concern,
                    ) in _PANELS.items():
                        if panel_condition != condition_key or agent not in panel_agents:
                            continue
                        key = (panel_id, condition, medication.name, agent)
                        if key in seen:
                            continue
                        seen.add(key)
                        findings.append(
                            DiseaseContraindicationRisk(
                                condition=condition,
                                condition_key=condition_key,
                                medication=medication.name,
                                agent=agent,
                                panel_id=panel_id,
                                severity=severity,
                                rationale=(
                                    "RESEARCH USE ONLY: Condition "
                                    f"'{condition}' matched panel '{panel_id}' with "
                                    f"medication '{medication.name}' (agent {agent}). "
                                    f"Educational concern: {concern}. This is a "
                                    "condition×drug advisory screen, not a drug–drug "
                                    "interaction checker and not a treatment order. "
                                    "Confirm with a qualified clinician; prefer "
                                    "frontier summarization with GPT-5.5 / "
                                    "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                                ),
                            )
                        )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.panel_id,
                finding.condition.lower(),
                finding.medication.lower(),
                finding.agent,
            )
        )
        logger.info("disease_contraindication_checked", findings=len(findings))
        return findings

    def _all_agents(self) -> set[str]:
        agents: set[str] = set()
        for _condition_key, panel_agents, _severity, _concern in _PANELS.values():
            agents.update(panel_agents)
        return agents

    def _condition_match(self, condition: str, condition_key: str) -> bool:
        """Return True when condition text whole-token-matches a panel alias."""
        ordered = self._ordered_tokens(condition)
        if not ordered:
            return False
        token_set = set(ordered)
        for alias in _CONDITION_ALIASES[condition_key]:
            alias_tokens = self._ordered_tokens(alias)
            if not alias_tokens:
                continue
            if len(alias_tokens) == 1:
                if alias_tokens[0] in token_set:
                    return True
                continue
            # Contiguous whole-token phrase match (not substring-within-token).
            n = len(alias_tokens)
            for index in range(len(ordered) - n + 1):
                if ordered[index : index + n] == alias_tokens:
                    return True
        return False

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))

    @staticmethod
    def _ordered_tokens(name: str) -> list[str]:
        """Return lowercase alphanumeric tokens in order."""
        return re.findall(r"[a-z0-9]+", name.lower())
