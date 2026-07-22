"""QTc drug-drug interaction safety checker.

The existing :mod:`qt_prolongation_checker` identifies individual
QT-prolonging medications and elevates severity when more than one distinct
QT-prolonging agent is present. Some combinations carry a more specific,
well-described synergistic risk than a simple additive count conveys: for
example methadone with ondansetron, or azithromycin with amiodarone.

This checker focuses on a conservative panel of named high-risk QTc
drug-drug interaction pairs. It emits one finding per unique canonical pair,
uses whole-token matching (never loose substrings), and is deterministic and
RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, QtcDdiRisk, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


class _QtcDdiPair:
    """A curated QTc drug-drug interaction panel entry.

    Attributes:
        pair_id: Stable panel identifier.
        agent_a: First canonical agent token.
        agent_b: Second canonical agent token.
        severity: Severity assigned when both agents are active.
        mechanism: Mechanism driving the synergistic QTc risk.
        clinical_consequence: Expected clinical hazard.
    """

    __slots__ = (
        "agent_a",
        "agent_b",
        "clinical_consequence",
        "mechanism",
        "pair_id",
        "severity",
    )

    def __init__(
        self,
        pair_id: str,
        agent_a: str,
        agent_b: str,
        severity: Severity,
        mechanism: str,
        clinical_consequence: str,
    ) -> None:
        """Initialize a QTc DDI panel pair."""
        self.pair_id = pair_id
        self.agent_a = agent_a
        self.agent_b = agent_b
        self.severity = severity
        self.mechanism = mechanism
        self.clinical_consequence = clinical_consequence

    @property
    def agents(self) -> frozenset[str]:
        """Return the unordered canonical agent pair."""
        return frozenset({self.agent_a, self.agent_b})


# Conservative high-risk QTc DDI panel. These are named pairs where the
# combination warrants more specific handling than a generic count of
# QT-prolonging agents.
_PAIR_PANEL: Final[tuple[_QtcDdiPair, ...]] = (
    _QtcDdiPair(
        "QTC-DDI-001",
        "azithromycin",
        "amiodarone",
        Severity.CRITICAL,
        "macrolide-associated repolarization delay plus class III antiarrhythmic effect",
        "marked QTc prolongation and torsades de pointes risk",
    ),
    _QtcDdiPair(
        "QTC-DDI-002",
        "clarithromycin",
        "amiodarone",
        Severity.CRITICAL,
        "CYP3A4 inhibition with additive QTc prolongation from a macrolide and amiodarone",
        "serious ventricular arrhythmia / torsades de pointes risk",
    ),
    _QtcDdiPair(
        "QTC-DDI-003",
        "erythromycin",
        "amiodarone",
        Severity.CRITICAL,
        "macrolide QTc effect and CYP3A4 inhibition layered on amiodarone exposure",
        "serious ventricular arrhythmia / torsades de pointes risk",
    ),
    _QtcDdiPair(
        "QTC-DDI-004",
        "methadone",
        "ondansetron",
        Severity.HIGH,
        "dose-dependent methadone QTc prolongation plus 5-HT3 antagonist QTc effect",
        "additive QTc prolongation and torsades de pointes risk",
    ),
    _QtcDdiPair(
        "QTC-DDI-005",
        "methadone",
        "azithromycin",
        Severity.HIGH,
        "two QT-prolonging agents with methadone's dose-dependent repolarization delay",
        "additive QTc prolongation and torsades de pointes risk",
    ),
    _QtcDdiPair(
        "QTC-DDI-006",
        "sotalol",
        "azithromycin",
        Severity.CRITICAL,
        "class III antiarrhythmic effect combined with macrolide-associated QTc prolongation",
        "marked QTc prolongation and torsades de pointes risk",
    ),
    _QtcDdiPair(
        "QTC-DDI-007",
        "dofetilide",
        "azithromycin",
        Severity.CRITICAL,
        "high-risk class III antiarrhythmic exposure plus macrolide QTc prolongation",
        "marked QTc prolongation and torsades de pointes risk",
    ),
    _QtcDdiPair(
        "QTC-DDI-008",
        "haloperidol",
        "azithromycin",
        Severity.HIGH,
        "antipsychotic and macrolide repolarization effects are additive",
        "QTc prolongation and torsades de pointes risk",
    ),
    _QtcDdiPair(
        "QTC-DDI-009",
        "citalopram",
        "ondansetron",
        Severity.HIGH,
        "SSRI dose-dependent QTc effect plus 5-HT3 antagonist QTc effect",
        "additive QTc prolongation and torsades de pointes risk",
    ),
    _QtcDdiPair(
        "QTC-DDI-010",
        "amiodarone",
        "moxifloxacin",
        Severity.CRITICAL,
        "class III antiarrhythmic effect combined with fluoroquinolone QTc prolongation",
        "marked QTc prolongation and torsades de pointes risk",
    ),
    _QtcDdiPair(
        "QTC-DDI-011",
        "fluconazole",
        "amiodarone",
        Severity.HIGH,
        "azole-associated QTc prolongation and CYP inhibition layered on amiodarone",
        "additive QTc prolongation and torsades de pointes risk",
    ),
)

_PANEL_AGENTS: Final[frozenset[str]] = frozenset(
    agent for pair in _PAIR_PANEL for agent in (pair.agent_a, pair.agent_b)
)


class QtcDdiChecker:
    """Flag named high-risk QTc-prolonging drug-drug interaction pairs."""

    def check(self, medications: list[Medication]) -> list[QtcDdiRisk]:
        """Return findings for known high-risk QTc DDI pairs.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`QtcDdiRisk` per unique matching canonical pair, ordered
            by descending severity then panel id. Duplicate entries for the same
            agent are de-duplicated, and a single medication entry naming both
            agents is not treated as a co-prescribed pair by itself.
        """
        agent_to_medications: dict[str, list[Medication]] = {}
        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue
            for agent in sorted(tokens & _PANEL_AGENTS):
                agent_to_medications.setdefault(agent, []).append(medication)

        findings: list[QtcDdiRisk] = []
        for pair in _PAIR_PANEL:
            matched_medications = self._select_distinct_medications(
                agent_to_medications.get(pair.agent_a, []),
                agent_to_medications.get(pair.agent_b, []),
            )
            if matched_medications is None:
                continue
            med_a, med_b = matched_medications
            findings.append(
                QtcDdiRisk(
                    medication_a=med_a.name,
                    medication_b=med_b.name,
                    agent_a=pair.agent_a,
                    agent_b=pair.agent_b,
                    pair_id=pair.pair_id,
                    severity=pair.severity,
                    mechanism=pair.mechanism,
                    clinical_consequence=pair.clinical_consequence,
                    rationale=(
                        f"Medications '{med_a.name}' ({pair.agent_a}) and '{med_b.name}' "
                        f"({pair.agent_b}) match {pair.pair_id}: {pair.mechanism}. "
                        f"Clinical concern: {pair.clinical_consequence}. Review the "
                        "combination and consider ECG/electrolyte monitoring."
                    ),
                )
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.pair_id))
        logger.info("qtc_ddi_checked", findings=len(findings))
        return findings

    @staticmethod
    def _select_distinct_medications(
        agent_a_medications: list[Medication],
        agent_b_medications: list[Medication],
    ) -> tuple[Medication, Medication] | None:
        """Choose the first two distinct medication entries for a candidate pair."""
        for medication_a in agent_a_medications:
            for medication_b in agent_b_medications:
                if medication_a is not medication_b:
                    return medication_a, medication_b
        return None

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name.

        Args:
            name: Medication name (may contain brand/dose/component separators).

        Returns:
            Set of component tokens.
        """
        return set(re.findall(r"[a-z0-9]+", name.lower()))
