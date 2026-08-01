"""Chemotherapy emetogenicity and antiemetic prophylaxis safety checker.

Highly and moderately emetogenic chemotherapy regimens require guideline-concordant
antiemetic prophylaxis to prevent acute and delayed chemotherapy-induced nausea
and vomiting (CINV). Missing prophylaxis or inadequate delayed-phase coverage
represents a preventable supportive-care gap distinct from lactation chemotherapy
flagging or QT-prolonging antiemetic surveillance.

This checker flags high/moderate emetogenic chemotherapy agents when antiemetic
prophylaxis cues are absent from the medication list, or when `days_since_chemo`
suggests the delayed-emesis window without delayed-phase antiemetic coverage.
Whole-token matching is used throughout. Findings are deterministic and RESEARCH
USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import ChemoEmesisRisk, Medication, Severity

logger = get_logger(__name__)

_DELAYED_PHASE_MIN_DAYS: Final[int] = 2
_DELAYED_PHASE_MAX_DAYS: Final[int] = 5

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_FINDING_KIND_RANK: Final[dict[str, int]] = {
    "missing_antiemetic_prophylaxis": 0,
    "delayed_phase_uncovered": 1,
}

# Canonical emetogenic chemo agent -> (emetogenic level, descriptor).
_EMETOGENIC_CHEMO_AGENTS: Final[dict[str, tuple[str, str]]] = {
    "cisplatin": ("high", "a highly emetogenic platinum chemotherapy agent"),
    "dacarbazine": ("high", "a highly emetogenic alkylating chemotherapy agent"),
    "ifosfamide": ("high", "a highly emetogenic alkylating chemotherapy agent"),
    "carboplatin": ("moderate", "a moderately emetogenic platinum chemotherapy agent"),
    "doxorubicin": ("moderate", "a moderately emetogenic anthracycline chemotherapy agent"),
    "cyclophosphamide": ("moderate", "a moderately emetogenic alkylating chemotherapy agent"),
    "oxaliplatin": ("moderate", "a moderately emetogenic platinum chemotherapy agent"),
}

# Canonical antiemetic agent -> short descriptor.
_ANTIEMETIC_AGENTS: Final[dict[str, str]] = {
    "ondansetron": "a 5-HT3 receptor antagonist antiemetic",
    "granisetron": "a 5-HT3 receptor antagonist antiemetic",
    "palonosetron": "a long-acting 5-HT3 receptor antagonist antiemetic",
    "aprepitant": "an NK1 receptor antagonist antiemetic",
    "fosaprepitant": "an IV NK1 receptor antagonist antiemetic prodrug",
    "dexamethasone": "a corticosteroid antiemetic",
    "olanzapine": "an atypical antipsychotic with antiemetic activity",
}

# Agents that provide delayed-phase CINV coverage.
_DELAYED_PHASE_ANTIEMETICS: Final[frozenset[str]] = frozenset(
    {"aprepitant", "fosaprepitant", "dexamethasone", "olanzapine"}
)


class ChemoEmesisChecker:
    """Flag emetogenic chemotherapy with missing or inadequate antiemetic prophylaxis."""

    def check(
        self,
        medications: list[Medication],
        days_since_chemo: int | None = None,
    ) -> list[ChemoEmesisRisk]:
        """Return findings for emetogenic chemo with inadequate antiemetic coverage.

        Args:
            medications: Active patient medications.
            days_since_chemo: Whole days since the most recent chemotherapy cycle,
                or None when unknown.

        Returns:
            One :class:`ChemoEmesisRisk` per emetogenic chemotherapy medication per
            applicable finding kind, ordered by descending severity then medication
            name and finding kind.
        """
        chemo_matches: list[tuple[Medication, str, str, str]] = []
        antiemetic_agents_found: set[str] = set()

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            chemo_candidates = [
                (agent, *_EMETOGENIC_CHEMO_AGENTS[agent])
                for agent in sorted(tokens & set(_EMETOGENIC_CHEMO_AGENTS))
            ]
            if chemo_candidates:
                agent, level, descriptor = chemo_candidates[0]
                chemo_matches.append((medication, agent, level, descriptor))

            antiemetic_agents_found.update(tokens & set(_ANTIEMETIC_AGENTS))

        if not chemo_matches:
            logger.info("chemo_emesis_checked", findings=0)
            return []

        findings: list[ChemoEmesisRisk] = []
        has_any_antiemetic = bool(antiemetic_agents_found)
        has_delayed_coverage = bool(antiemetic_agents_found & _DELAYED_PHASE_ANTIEMETICS)
        in_delayed_window = (
            days_since_chemo is not None
            and _DELAYED_PHASE_MIN_DAYS <= days_since_chemo <= _DELAYED_PHASE_MAX_DAYS
        )

        for medication, agent, level, descriptor in chemo_matches:
            if not has_any_antiemetic:
                findings.append(
                    self._build_finding(
                        medication_name=medication.name,
                        agent=agent,
                        descriptor=descriptor,
                        emetogenic_level=level,
                        finding_kind="missing_antiemetic_prophylaxis",
                        days_since_chemo=days_since_chemo,
                        antiemetic_agents_found=sorted(antiemetic_agents_found),
                    )
                )

            if in_delayed_window and not has_delayed_coverage:
                findings.append(
                    self._build_finding(
                        medication_name=medication.name,
                        agent=agent,
                        descriptor=descriptor,
                        emetogenic_level=level,
                        finding_kind="delayed_phase_uncovered",
                        days_since_chemo=days_since_chemo,
                        antiemetic_agents_found=sorted(antiemetic_agents_found),
                    )
                )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.medication.lower(),
                _FINDING_KIND_RANK[finding.finding_kind],
                finding.agent,
            )
        )
        logger.info(
            "chemo_emesis_checked",
            findings=len(findings),
            chemo_agents=len({agent for _med, agent, _lvl, _desc in chemo_matches}),
            antiemetics=len(antiemetic_agents_found),
        )
        return findings

    def _build_finding(
        self,
        *,
        medication_name: str,
        agent: str,
        descriptor: str,
        emetogenic_level: str,
        finding_kind: str,
        days_since_chemo: int | None,
        antiemetic_agents_found: list[str],
    ) -> ChemoEmesisRisk:
        """Construct a single chemo-emesis finding."""
        return ChemoEmesisRisk(
            medication=medication_name,
            agent=agent,
            finding_kind=finding_kind,
            severity=self._severity_for(emetogenic_level, finding_kind),
            emetogenic_level=emetogenic_level,
            days_since_chemo=days_since_chemo,
            antiemetic_agents_found=antiemetic_agents_found,
            rationale=self._build_rationale(
                medication_name=medication_name,
                agent=agent,
                descriptor=descriptor,
                emetogenic_level=emetogenic_level,
                finding_kind=finding_kind,
                days_since_chemo=days_since_chemo,
                antiemetic_agents_found=antiemetic_agents_found,
            ),
        )

    @staticmethod
    def _severity_for(emetogenic_level: str, finding_kind: str) -> Severity:
        """Map emetogenic level and finding kind to advisory severity."""
        if finding_kind == "missing_antiemetic_prophylaxis":
            return Severity.CRITICAL if emetogenic_level == "high" else Severity.HIGH
        return Severity.HIGH if emetogenic_level == "high" else Severity.MODERATE

    @staticmethod
    def _build_rationale(
        *,
        medication_name: str,
        agent: str,
        descriptor: str,
        emetogenic_level: str,
        finding_kind: str,
        days_since_chemo: int | None,
        antiemetic_agents_found: list[str],
    ) -> str:
        """Compose a RESEARCH USE ONLY chemo-emesis rationale."""
        if finding_kind == "missing_antiemetic_prophylaxis":
            detail = (
                "no antiemetic prophylaxis agents (ondansetron, granisetron, "
                "palonosetron, aprepitant, fosaprepitant, dexamethasone, olanzapine) "
                "are documented on the medication list"
            )
        else:
            detail = (
                f"day {days_since_chemo} after chemotherapy falls in the delayed CINV "
                f"window (days {_DELAYED_PHASE_MIN_DAYS}–{_DELAYED_PHASE_MAX_DAYS}) "
                "without documented delayed-phase coverage (aprepitant, fosaprepitant, "
                "dexamethasone, or olanzapine)"
            )
            if antiemetic_agents_found:
                detail += (
                    f"; acute antiemetics present ({', '.join(antiemetic_agents_found)}) "
                    "do not substitute for delayed-phase prophylaxis"
                )

        return (
            "RESEARCH USE ONLY: "
            f"Medication '{medication_name}' contains {agent}, {descriptor}, "
            f"classified as {emetogenic_level} emetogenicity. {detail.capitalize()}. "
            "Guideline-concordant antiemetic prophylaxis reduces acute and delayed "
            "chemotherapy-induced nausea and vomiting. Review antiemetic orders and "
            "supportive-care plan before the next cycle."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
