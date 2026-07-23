"""Combined renal + hepatic safety checker.

Dual organ impairment is a common clinical decision support gap: a medication
may be individually risky in reduced kidney function and in hepatic impairment,
and the combination deserves a distinct, high-salience advisory. This checker
composes :class:`RenalDoseChecker` and :class:`HepaticDoseChecker` and emits a
finding only when the same active medication and canonical agent trigger both
component checkers for the same patient context.

The checker is deterministic, uses the component checkers' whole-token matching,
and is RESEARCH USE ONLY. It does not infer missing organ-function data: an
unknown eGFR or unknown Child-Pugh class yields no combined findings.
"""

from __future__ import annotations

from medagent.logging_config import get_logger
from medagent.models import CombinedRenalHepaticRisk, HepaticFunction, Medication, Severity
from medagent.safety.hepatic_dose_checker import HepaticDoseChecker
from medagent.safety.renal_dose_checker import RenalDoseChecker

logger = get_logger(__name__)

# Higher rank = more severe, used for max-severity selection and ordering.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


class CombinedRenalHepaticChecker:
    """Flag medications with concurrent renal-dose and hepatic-dose concerns."""

    def __init__(
        self,
        renal_checker: RenalDoseChecker | None = None,
        hepatic_checker: HepaticDoseChecker | None = None,
    ) -> None:
        """Initialize the combined checker.

        Args:
            renal_checker: Optional renal-dose checker dependency. Supplying one
                is useful for tests or alternate curated panels.
            hepatic_checker: Optional hepatic-dose checker dependency. Supplying
                one is useful for tests or alternate curated panels.
        """
        self._renal_checker = renal_checker or RenalDoseChecker()
        self._hepatic_checker = hepatic_checker or HepaticDoseChecker()

    def check(
        self,
        medications: list[Medication],
        egfr: float | None,
        hepatic_function: HepaticFunction | None,
    ) -> list[CombinedRenalHepaticRisk]:
        """Return dual renal + hepatic safety findings for active medications.

        A combined finding is produced only when both organ-function inputs are
        known and the same medication/agent appears in both component checkers'
        findings. The combined severity is the maximum of the two component
        severities.

        Args:
            medications: Active patient medications.
            egfr: Estimated glomerular filtration rate in mL/min/1.73m^2, or
                None when unknown.
            hepatic_function: Patient hepatic-function class (Child-Pugh), or
                None when unknown.

        Returns:
            One :class:`CombinedRenalHepaticRisk` per dual-organ medication,
            ordered by descending combined severity then medication name and
            agent. Unknown eGFR or unknown hepatic function returns an empty
            list even if one component checker alone would flag a medication.
        """
        if egfr is None or hepatic_function is None:
            logger.info("combined_renal_hepatic_checked", findings=0, eligible=False)
            return []

        renal_findings = self._renal_checker.check(medications=medications, egfr=egfr)
        hepatic_findings = self._hepatic_checker.check(
            medications=medications,
            hepatic_function=hepatic_function,
        )

        renal_by_medication_agent = {
            (finding.medication, finding.agent): finding for finding in renal_findings
        }

        findings: list[CombinedRenalHepaticRisk] = []
        for hepatic in hepatic_findings:
            renal = renal_by_medication_agent.get((hepatic.medication, hepatic.agent))
            if renal is None:
                continue

            severity = self._max_severity(renal.severity, hepatic.severity)
            rationale = (
                "RESEARCH USE ONLY: "
                f"Medication '{hepatic.medication}' contains {hepatic.agent}, which triggered "
                "both renal-dose and hepatic-dose safety concerns for this patient. "
                f"Renal component: eGFR {renal.egfr:g} mL/min/1.73m^2 at/below threshold "
                f"{renal.threshold_egfr:g}; action {renal.action}; severity "
                f"{renal.severity.value}. Hepatic component: {hepatic.hepatic_function.value} "
                f"Child-Pugh class at/above threshold {hepatic.threshold_function.value}; action "
                f"{hepatic.action}; severity {hepatic.severity.value}. Review both organ-function "
                "constraints with a qualified clinician before any clinical use."
            )
            findings.append(
                CombinedRenalHepaticRisk(
                    medication=hepatic.medication,
                    agent=hepatic.agent,
                    egfr=renal.egfr,
                    threshold_egfr=renal.threshold_egfr,
                    hepatic_function=hepatic.hepatic_function,
                    threshold_function=hepatic.threshold_function,
                    renal_action=renal.action,
                    hepatic_action=hepatic.action,
                    renal_severity=renal.severity,
                    hepatic_severity=hepatic.severity,
                    severity=severity,
                    rationale=rationale,
                )
            )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.medication,
                finding.agent,
            )
        )
        logger.info("combined_renal_hepatic_checked", findings=len(findings), eligible=True)
        return findings

    @staticmethod
    def _max_severity(first: Severity, second: Severity) -> Severity:
        """Return the higher-ranked severity.

        Args:
            first: First component severity.
            second: Second component severity.

        Returns:
            The severity with the higher clinical rank; ties return ``first``.
        """
        if _SEVERITY_RANK[first] >= _SEVERITY_RANK[second]:
            return first
        return second
