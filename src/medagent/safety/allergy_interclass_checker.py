"""Allergy inter-class cross-reactivity checker.

The existing :class:`~medagent.safety.allergy_checker.AllergyChecker` flags
**direct** substance matches and **intra-class** cross-reactivity (for example
penicillin ↔ amoxicillin). It deliberately does **not** model inter-class
hazards such as penicillin allergy ↔ cephalosporin medication, to avoid noisy
false alarms in the primary allergy screen.

This checker fills that educational gap with a small, curated panel of
well-documented **inter-class** cross-reactivity pairs (β-lactam side-chain /
class relationships and a few analogous educational screens). Findings are
advisory RESEARCH USE ONLY records and never modify medications.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import AllergyInterClassRisk, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Allergy-side class token sets (matched as whole tokens in allergy text).
_ALLERGY_CLASSES: Final[dict[str, frozenset[str]]] = {
    "penicillins": frozenset(
        {
            "penicillin",
            "amoxicillin",
            "ampicillin",
            "piperacillin",
            "dicloxacillin",
            "nafcillin",
            "oxacillin",
            "augmentin",
            "penicillins",
        }
    ),
    "cephalosporins": frozenset(
        {
            "cephalexin",
            "cefazolin",
            "ceftriaxone",
            "cefuroxime",
            "cefdinir",
            "cefepime",
            "cefixime",
            "cephalosporin",
            "cephalosporins",
        }
    ),
    "sulfonamides": frozenset(
        {
            "sulfamethoxazole",
            "sulfadiazine",
            "sulfasalazine",
            "bactrim",
            "cotrimoxazole",
            "sulfonamide",
            "sulfonamides",
            "sulfa",
        }
    ),
}

# Medication-side class token sets (matched as whole tokens in medication names).
_MED_CLASSES: Final[dict[str, frozenset[str]]] = {
    "cephalosporins": frozenset(
        {
            "cephalexin",
            "cefazolin",
            "ceftriaxone",
            "cefuroxime",
            "cefdinir",
            "cefepime",
            "cefixime",
            "cephalosporin",
        }
    ),
    "carbapenems": frozenset(
        {
            "meropenem",
            "imipenem",
            "ertapenem",
            "doripenem",
            "carbapenem",
        }
    ),
    "penicillins": frozenset(
        {
            "penicillin",
            "amoxicillin",
            "ampicillin",
            "piperacillin",
            "dicloxacillin",
            "nafcillin",
            "oxacillin",
            "augmentin",
        }
    ),
    "non_antibiotic_sulfonamides": frozenset(
        {
            "furosemide",
            "hydrochlorothiazide",
            "hctz",
            "acetazolamide",
            "celecoxib",
            "probenecid",
        }
    ),
}

# panel_id -> (allergy_class, med_class, severity, concern)
_PANELS: Final[dict[str, tuple[str, str, Severity, str]]] = {
    "penicillin_cephalosporin": (
        "penicillins",
        "cephalosporins",
        Severity.MODERATE,
        "possible β-lactam inter-class cross-reactivity (penicillin allergy ↔ cephalosporin)",
    ),
    "penicillin_carbapenem": (
        "penicillins",
        "carbapenems",
        Severity.LOW,
        "low-rate β-lactam inter-class cross-reactivity (penicillin allergy ↔ carbapenem)",
    ),
    "cephalosporin_penicillin": (
        "cephalosporins",
        "penicillins",
        Severity.MODERATE,
        "possible β-lactam inter-class cross-reactivity (cephalosporin allergy ↔ penicillin)",
    ),
    "sulfonamide_non_antibiotic": (
        "sulfonamides",
        "non_antibiotic_sulfonamides",
        Severity.LOW,
        "educational sulfonamide allergy ↔ non-antibiotic sulfonamide structural caution "
        "(cross-reactivity is uncommon but often reviewed)",
    ),
}


class AllergyInterClassCrossReactivityChecker:
    """Flag curated inter-class allergy × medication cross-reactivity risks."""

    def check(
        self,
        medications: list[Medication],
        allergies: list[str],
    ) -> list[AllergyInterClassRisk]:
        """Return advisory inter-class cross-reactivity findings.

        Args:
            medications: Active medications.
            allergies: Documented allergy substance / class strings.

        Returns:
            One :class:`AllergyInterClassRisk` per unique
            (panel_id, allergy, medication, allergy_agent, med_agent) match,
            ordered by descending severity then panel id and names.
            Matching uses whole-token logic. Intra-class pairs are out of scope
            (handled by :class:`AllergyChecker`).
        """
        allergy_hits: list[tuple[str, str, str]] = []
        for allergy in allergies:
            tokens = self._tokens(allergy)
            if not tokens:
                continue
            for class_name, members in _ALLERGY_CLASSES.items():
                matched = sorted(tokens & members)
                if matched:
                    allergy_hits.append((allergy, class_name, matched[0]))

        if not allergy_hits:
            logger.info("allergy_interclass_checked", findings=0)
            return []

        findings: list[AllergyInterClassRisk] = []
        seen: set[tuple[str, str, str, str, str]] = set()

        for medication in medications:
            med_tokens = self._tokens(medication.name)
            if not med_tokens:
                continue
            for med_class, members in _MED_CLASSES.items():
                med_agents = sorted(med_tokens & members)
                if not med_agents:
                    continue
                med_agent = med_agents[0]
                for allergy, allergy_class, allergy_agent in allergy_hits:
                    for panel_id, (
                        panel_allergy_class,
                        panel_med_class,
                        severity,
                        concern,
                    ) in _PANELS.items():
                        if panel_allergy_class != allergy_class or panel_med_class != med_class:
                            continue
                        key = (
                            panel_id,
                            allergy,
                            medication.name,
                            allergy_agent,
                            med_agent,
                        )
                        if key in seen:
                            continue
                        seen.add(key)
                        findings.append(
                            AllergyInterClassRisk(
                                allergy=allergy,
                                allergy_class=allergy_class,
                                allergy_agent=allergy_agent,
                                medication=medication.name,
                                medication_class=med_class,
                                medication_agent=med_agent,
                                panel_id=panel_id,
                                severity=severity,
                                rationale=(
                                    "RESEARCH USE ONLY: Documented allergy "
                                    f"'{allergy}' (class {allergy_class}, agent "
                                    f"{allergy_agent}) matched inter-class panel "
                                    f"'{panel_id}' with medication "
                                    f"'{medication.name}' (class {med_class}, "
                                    f"agent {med_agent}). Educational concern: "
                                    f"{concern}. This is an inter-class advisory "
                                    "screen distinct from intra-class "
                                    "AllergyChecker findings and not a treatment "
                                    "order. Confirm with a qualified clinician; "
                                    "prefer frontier summarization with GPT-5.5 / "
                                    "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                                ),
                            )
                        )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.panel_id,
                finding.allergy.lower(),
                finding.medication.lower(),
            )
        )
        logger.info("allergy_interclass_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
