"""QT-prolongation safety checker.

Several widely prescribed drugs prolong the cardiac QT interval and, in
combination or at risk-elevated doses, can precipitate torsades de pointes — a
potentially fatal ventricular arrhythmia. The hazard is neither a classic
drug-drug interaction of two named agents, an allergy, a duplicate therapy, nor
a pregnancy risk, so it is not surfaced by the existing checkers.

This checker flags each active medication that matches a known QT-prolonging
agent. Because torsadogenic risk is *additive*, a finding's severity is elevated
when two or more QT-prolonging medications are co-prescribed. It uses whole-token
matching (never loose substrings) and a conservative, well-established agent list
drawn from the CredibleMeds "known risk" category. It is deterministic and
RESEARCH USE ONLY, complementing the drug-drug interaction, drug-allergy,
duplicate-therapy, and pregnancy-safety checkers.
"""

from __future__ import annotations

import re

from medagent.logging_config import get_logger
from medagent.models import Medication, QTProlongationRisk, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical QT-prolonging agent token -> (baseline severity, short rationale).
# Agents are matched as whole component tokens of a medication name. Baseline
# severity applies to the agent alone; co-prescription elevates it (see check()).
_QT_PROLONGING_AGENTS: dict[str, tuple[Severity, str]] = {
    # Antiarrhythmics — the highest baseline torsadogenic risk.
    "amiodarone": (Severity.HIGH, "a class III antiarrhythmic with marked QT prolongation"),
    "sotalol": (Severity.HIGH, "a class III antiarrhythmic with dose-dependent QT prolongation"),
    "dofetilide": (Severity.HIGH, "a class III antiarrhythmic with high torsades risk"),
    "quinidine": (Severity.HIGH, "a class Ia antiarrhythmic with high torsades risk"),
    "procainamide": (Severity.HIGH, "a class Ia antiarrhythmic that prolongs the QT interval"),
    # Opioid — long-acting, dose-dependent QT prolongation.
    "methadone": (Severity.HIGH, "a long-acting opioid with dose-dependent QT prolongation"),
    # Antipsychotics.
    "haloperidol": (Severity.MODERATE, "an antipsychotic with dose-dependent QT prolongation"),
    "thioridazine": (Severity.HIGH, "an antipsychotic with marked QT prolongation"),
    "ziprasidone": (Severity.MODERATE, "an antipsychotic that prolongs the QT interval"),
    # SSRIs / antidepressants.
    "citalopram": (Severity.MODERATE, "an SSRI with dose-dependent QT prolongation"),
    "escitalopram": (Severity.MODERATE, "an SSRI that prolongs the QT interval"),
    # Macrolide and fluoroquinolone antibiotics.
    "azithromycin": (Severity.MODERATE, "a macrolide antibiotic that prolongs the QT interval"),
    "clarithromycin": (Severity.MODERATE, "a macrolide antibiotic that prolongs the QT interval"),
    "erythromycin": (Severity.MODERATE, "a macrolide antibiotic that prolongs the QT interval"),
    "moxifloxacin": (Severity.MODERATE, "a fluoroquinolone with notable QT prolongation"),
    "levofloxacin": (Severity.MODERATE, "a fluoroquinolone that prolongs the QT interval"),
    "ciprofloxacin": (Severity.MODERATE, "a fluoroquinolone that prolongs the QT interval"),
    # Antiemetic and antifungal.
    "ondansetron": (Severity.MODERATE, "an antiemetic with dose-dependent QT prolongation"),
    "fluconazole": (Severity.MODERATE, "an azole antifungal that prolongs the QT interval"),
}


class QTProlongationChecker:
    """Flag active medications that prolong the QT interval."""

    def check(self, medications: list[Medication]) -> list[QTProlongationRisk]:
        """Return one finding per medication that matches a QT-prolonging agent.

        Torsadogenic risk is additive, so when two or more QT-prolonging
        medications are present, every finding's severity is elevated to at least
        HIGH and its rationale notes the additive risk.

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`QTProlongationRisk` per medication matching a
            QT-prolonging agent, ordered by descending severity then medication
            name. When a medication matches more than one agent, the
            highest-baseline-severity agent is reported.
        """
        matched_medications: list[tuple[Medication, str, Severity, str]] = []
        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue
            candidates = [
                (agent, *_QT_PROLONGING_AGENTS[agent])
                for agent in tokens & set(_QT_PROLONGING_AGENTS)
            ]
            if not candidates:
                continue
            agent, severity, reason = max(
                candidates, key=lambda item: (_SEVERITY_RANK[item[1]], item[0])
            )
            matched_medications.append((medication, agent, severity, reason))

        qt_medication_count = len(matched_medications)
        findings: list[QTProlongationRisk] = []
        for medication, agent, severity, reason in matched_medications:
            concurrent = qt_medication_count - 1
            effective_severity = severity
            if concurrent >= 1 and _SEVERITY_RANK[severity] < _SEVERITY_RANK[Severity.HIGH]:
                effective_severity = Severity.HIGH
            if concurrent >= 1:
                rationale = (
                    f"Medication '{medication.name}' contains {agent}, which is {reason}. "
                    f"It is co-prescribed with {concurrent} other QT-prolonging "
                    "medication(s); additive risk of torsades de pointes — review the "
                    "combination and consider ECG/electrolyte monitoring."
                )
            else:
                rationale = (
                    f"Medication '{medication.name}' contains {agent}, which is {reason}; "
                    "review QT-interval risk, especially with electrolyte disturbance or "
                    "at higher doses."
                )
            findings.append(
                QTProlongationRisk(
                    medication=medication.name,
                    agent=agent,
                    severity=effective_severity,
                    concurrent_qt_medications=concurrent,
                    rationale=rationale,
                )
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.medication))
        logger.info("qt_prolongation_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name.

        Args:
            name: Medication name (may contain brand/dose/component separators).

        Returns:
            Set of component tokens.
        """
        return set(re.findall(r"[a-z0-9]+", name.lower()))
