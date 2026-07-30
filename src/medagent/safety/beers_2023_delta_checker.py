"""2023 AGS Beers Criteria update-delta safety checker.

The American Geriatrics Society (AGS) Beers Criteria were updated in 2023 with
several new or strengthened avoid/caution recommendations relative to the prior
edition. Examples include avoiding initiation of aspirin for primary
cardiovascular prevention, preferring DOACs over warfarin as initial therapy
for most nonvalvular AF / VTE cases, using rivaroxaban and dabigatran with
caution for higher GI bleeding risk, expanding sulfonylurea avoidance beyond
long-acting agents (e.g. glipizide), adding SNRIs to the falls/fractures
caution table, and avoiding concurrent opioids with gabapentinoids.

This checker complements :class:`~medagent.safety.beers_criteria_checker.BeersCriteriaChecker`,
which covers the classic older-adult PIM panel. It focuses only on a
conservative curated educational/demo catalog of **2023 deltas**, applies only
to patients aged 65 and older, uses whole-token matching (never loose
substrings), and is deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Beers2023DeltaRisk, Medication, Severity

logger = get_logger(__name__)

# The Beers Criteria apply to older adults; this is the standard age threshold.
_OLDER_ADULT_AGE_THRESHOLD: Final[int] = 65

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical 2023-delta agent -> (delta_kind, category, severity, update_summary, concern).
# Intentionally excludes classic long-standing Beers agents already covered by
# BeersCriteriaChecker (e.g. diazepam, glyburide, diphenhydramine).
_DELTA_AGENTS: Final[dict[str, tuple[str, str, Severity, str, str]]] = {
    # 2023: avoid initiating aspirin for primary CVD prevention.
    "aspirin": (
        "new_avoid",
        "antiplatelet",
        Severity.HIGH,
        "2023 update: avoid initiating aspirin for primary cardiovascular prevention",
        "bleeding risk outweighs benefit when used for primary prevention",
    ),
    # 2023: prefer DOAC over warfarin as initial therapy for most NVAF/VTE.
    "warfarin": (
        "new_avoid",
        "vitamin K antagonist",
        Severity.HIGH,
        "2023 update: prefer a DOAC over warfarin as initial therapy for most NVAF/VTE",
        "preferential DOAC initiation unless warfarin-specific indication applies",
    ),
    # 2023: rivaroxaban / dabigatran use-with-caution (higher major GI bleed vs other DOACs).
    "rivaroxaban": (
        "new_caution",
        "direct oral anticoagulant",
        Severity.MODERATE,
        "2023 update: use rivaroxaban with caution due to higher major GI bleeding risk",
        "higher major gastrointestinal bleeding risk versus other DOACs",
    ),
    "dabigatran": (
        "new_caution",
        "direct oral anticoagulant",
        Severity.MODERATE,
        "2023 update: use dabigatran with caution due to higher GI bleeding risk",
        "higher gastrointestinal bleeding risk versus other DOACs",
    ),
    # 2023: sulfonylurea avoidance expanded beyond long-acting agents.
    "glipizide": (
        "expanded_avoid",
        "sulfonylurea",
        Severity.HIGH,
        "2023 update: sulfonylurea avoidance expanded beyond long-acting agents",
        "hypoglycaemia risk in older adults",
    ),
    "glimepiride": (
        "expanded_avoid",
        "sulfonylurea",
        Severity.HIGH,
        "2023 update: sulfonylurea avoidance expanded beyond long-acting agents",
        "hypoglycaemia risk in older adults",
    ),
    # 2023: SNRIs added to falls/fractures caution table.
    "duloxetine": (
        "new_caution",
        "SNRI",
        Severity.MODERATE,
        "2023 update: SNRIs added to the falls and fractures caution table",
        "increased fall and fracture risk",
    ),
    "venlafaxine": (
        "new_caution",
        "SNRI",
        Severity.MODERATE,
        "2023 update: SNRIs added to the falls and fractures caution table",
        "increased fall and fracture risk",
    ),
    "desvenlafaxine": (
        "new_caution",
        "SNRI",
        Severity.MODERATE,
        "2023 update: SNRIs added to the falls and fractures caution table",
        "increased fall and fracture risk",
    ),
}

# 2023 concurrent-avoid: opioids with gabapentinoids (except carefully supervised transitions).
_OPIOID_AGENTS: Final[frozenset[str]] = frozenset(
    {
        "codeine",
        "fentanyl",
        "hydrocodone",
        "hydromorphone",
        "meperidine",
        "methadone",
        "morphine",
        "oxycodone",
        "oxymorphone",
        "tapentadol",
        "tramadol",
    }
)

_GABAPENTINOID_AGENTS: Final[frozenset[str]] = frozenset({"gabapentin", "pregabalin"})

# Aspirin primary-prevention avoid is suppressed when secondary-prevention cues exist.
_SECONDARY_PREVENTION_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "acs",
        "acute coronary syndrome",
        "cabg",
        "cad",
        "coronary artery disease",
        "mi",
        "myocardial infarction",
        "pci",
        "secondary prevention",
        "stent",
        "stroke",
        "tia",
        "transient ischemic attack",
    }
)


class Beers2023DeltaChecker:
    """Flag 2023 AGS Beers Criteria update deltas for older adults."""

    def check(
        self,
        medications: list[Medication],
        age: int | None,
        *,
        conditions: list[str] | None = None,
    ) -> list[Beers2023DeltaRisk]:
        """Return 2023 Beers update-delta findings for an older adult.

        The Beers Criteria apply only to adults aged 65 and older, so no finding
        is returned for a younger patient or when the age is unknown. Aspirin
        primary-prevention findings are suppressed when ``conditions`` document a
        secondary-prevention indication.

        Args:
            medications: Active patient medications.
            age: Patient age in years, or None when unknown.
            conditions: Optional free-text conditions/indications used to suppress
                aspirin primary-prevention findings when secondary prevention is
                documented.

        Returns:
            One :class:`Beers2023DeltaRisk` per matching delta (single-agent or
            concurrent opioid × gabapentinoid pair), ordered by descending
            severity then medication name. An empty list is returned for patients
            under 65, unknown age, or when no 2023-delta agent matches.
        """
        if age is None or age < _OLDER_ADULT_AGE_THRESHOLD:
            logger.info("beers_2023_delta_checked", findings=0, eligible=False)
            return []

        suppress_aspirin = self._has_secondary_prevention(conditions)
        findings: list[Beers2023DeltaRisk] = []

        for medication in medications:
            tokens = self._tokens(medication.name)
            matched_agents = sorted(tokens & set(_DELTA_AGENTS))
            if not matched_agents:
                continue
            agent = matched_agents[0]
            if agent == "aspirin" and suppress_aspirin:
                continue
            delta_kind, category, severity, update_summary, concern = _DELTA_AGENTS[agent]
            rationale = (
                "RESEARCH USE ONLY: "
                f"Medication '{medication.name}' contains {agent}, a {category} matching a "
                f"2023 AGS Beers Criteria update delta ({delta_kind}) for adults aged "
                f"{_OLDER_ADULT_AGE_THRESHOLD} and older (patient age {age}). "
                f"{update_summary}. Primary concern: {concern}. Review indication and "
                "safer alternatives with a qualified clinician before any medication change."
            )
            findings.append(
                Beers2023DeltaRisk(
                    medication=medication.name,
                    agent=agent,
                    delta_kind=delta_kind,
                    beers_category=category,
                    update_summary=update_summary,
                    severity=severity,
                    patient_age=age,
                    rationale=rationale,
                )
            )

        findings.extend(self._concurrent_opioid_gabapentinoid_findings(medications, age))

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.medication,
                finding.agent,
                finding.agent_b or "",
            )
        )
        logger.info("beers_2023_delta_checked", findings=len(findings), eligible=True)
        return findings

    def _concurrent_opioid_gabapentinoid_findings(
        self,
        medications: list[Medication],
        age: int,
    ) -> list[Beers2023DeltaRisk]:
        """Return findings for 2023 concurrent opioid × gabapentinoid avoid deltas."""
        opioid_hits: list[tuple[str, Medication]] = []
        gabapentinoid_hits: list[tuple[str, Medication]] = []
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _OPIOID_AGENTS):
                opioid_hits.append((agent, medication))
            for agent in sorted(tokens & _GABAPENTINOID_AGENTS):
                gabapentinoid_hits.append((agent, medication))

        findings: list[Beers2023DeltaRisk] = []
        seen_pairs: set[tuple[str, str]] = set()
        for opioid_agent, opioid_med in opioid_hits:
            for gaba_agent, gaba_med in gabapentinoid_hits:
                if opioid_med is gaba_med:
                    continue
                pair_key = (opioid_agent, gaba_agent)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                update_summary = (
                    "2023 update: avoid concurrent opioids with gabapentinoids except "
                    "during carefully supervised transitions"
                )
                findings.append(
                    Beers2023DeltaRisk(
                        medication=opioid_med.name,
                        agent=opioid_agent,
                        delta_kind="concurrent_avoid",
                        beers_category="opioid–gabapentinoid combination",
                        update_summary=update_summary,
                        severity=Severity.HIGH,
                        patient_age=age,
                        medication_b=gaba_med.name,
                        agent_b=gaba_agent,
                        rationale=(
                            "RESEARCH USE ONLY: "
                            f"Medications '{opioid_med.name}' ({opioid_agent}) and "
                            f"'{gaba_med.name}' ({gaba_agent}) match a 2023 AGS Beers "
                            f"Criteria concurrent-avoid delta for adults aged "
                            f"{_OLDER_ADULT_AGE_THRESHOLD} and older (patient age {age}). "
                            f"{update_summary}. Primary concern: additive sedation, "
                            "respiratory depression, and overdose risk. Review with a "
                            "qualified clinician before any medication change."
                        ),
                    )
                )
        return findings

    @staticmethod
    def _has_secondary_prevention(conditions: list[str] | None) -> bool:
        """Return True when documented conditions imply secondary prevention."""
        if not conditions:
            return False
        haystack = " ".join(conditions).lower()
        for alias in _SECONDARY_PREVENTION_ALIASES:
            if alias in haystack:
                return True
        return False

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name.

        Args:
            name: Medication name (may contain brand/dose/component separators).

        Returns:
            Set of component tokens.
        """
        return set(re.findall(r"[a-z0-9]+", name.lower()))
