"""Combined renal + hepatic + lactation medication-safety checker.

Patients with kidney and/or liver impairment who are also breastfeeding may need
a unified view of organ-function dose cautions and infant milk-transfer hazards.
The standalone renal-dose, hepatic-dose, combined renal+hepatic, and lactation
checkers each cover one slice of that picture; this checker composes the organ
and lactation domains and surfaces three finding kinds:

* **combined** — the same medication triggers organ-impairment (renal and/or
  hepatic) and lactation concerns when ``breastfeeding=True`` (severity is
  escalated one rank, capped at ``CRITICAL``);
* **organ_only** — renal and/or hepatic dose concern without lactation;
* **lactation_only** — breastfeeding concern without organ impairment.

The checker is deterministic, reuses the curated panels from
:class:`RenalDoseChecker`, :class:`HepaticDoseChecker`, and
:class:`LactationSafetyChecker`, and is RESEARCH USE ONLY.
"""

from __future__ import annotations

from dataclasses import dataclass

from medagent.logging_config import get_logger
from medagent.models import (
    HepaticDoseRisk,
    HepaticFunction,
    LactationRisk,
    Medication,
    RenalDoseRisk,
    RenalHepaticLactationConcernKind,
    RenalHepaticLactationRisk,
    Severity,
)
from medagent.safety.hepatic_dose_checker import HepaticDoseChecker
from medagent.safety.lactation_checker import LactationSafetyChecker
from medagent.safety.renal_dose_checker import RenalDoseChecker

logger = get_logger(__name__)

# Higher rank = more severe, used for ordering and escalation.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_CONCERN_KIND_RANK: dict[RenalHepaticLactationConcernKind, int] = {
    RenalHepaticLactationConcernKind.COMBINED: 2,
    RenalHepaticLactationConcernKind.ORGAN_ONLY: 1,
    RenalHepaticLactationConcernKind.LACTATION_ONLY: 0,
}

# Escalate combined findings one severity rank above the component maximum.
_COMBINED_ESCALATION: dict[Severity, Severity] = {
    Severity.UNKNOWN: Severity.LOW,
    Severity.LOW: Severity.MODERATE,
    Severity.MODERATE: Severity.HIGH,
    Severity.HIGH: Severity.CRITICAL,
    Severity.CRITICAL: Severity.CRITICAL,
}


@dataclass(frozen=True)
class _OrganFinding:
    """Merged renal and/or hepatic findings for one medication display name."""

    medication: str
    agent: str
    renal: RenalDoseRisk | None
    hepatic: HepaticDoseRisk | None
    severity: Severity


class RenalHepaticLactationChecker:
    """Flag medications with organ-impairment, lactation, or dual concerns."""

    def __init__(
        self,
        renal_checker: RenalDoseChecker | None = None,
        hepatic_checker: HepaticDoseChecker | None = None,
        lactation_checker: LactationSafetyChecker | None = None,
    ) -> None:
        """Initialize the combined checker.

        Args:
            renal_checker: Optional renal-dose checker dependency for tests or
                alternate curated panels.
            hepatic_checker: Optional hepatic-dose checker dependency for tests
                or alternate curated panels.
            lactation_checker: Optional lactation checker dependency for tests
                or alternate curated panels.
        """
        self._renal_checker = renal_checker or RenalDoseChecker()
        self._hepatic_checker = hepatic_checker or HepaticDoseChecker()
        self._lactation_checker = lactation_checker or LactationSafetyChecker()

    def check(
        self,
        medications: list[Medication],
        egfr: float | None,
        hepatic_function: HepaticFunction | None,
        breastfeeding: bool,
    ) -> list[RenalHepaticLactationRisk]:
        """Return unified organ-impairment and/or lactation safety findings.

        Args:
            medications: Active patient medications.
            egfr: Estimated glomerular filtration rate in mL/min/1.73m^2, or
                None when unknown.
            hepatic_function: Patient hepatic-function class (Child-Pugh), or
                None when unknown.
            breastfeeding: Whether the patient is documented as breastfeeding /
                lactating.

        Returns:
            One :class:`RenalHepaticLactationRisk` per flagged medication.
            Combined findings are emitted only when breastfeeding is documented
            and the same medication appears in both organ and lactation
            findings. Findings are ordered by concern kind (combined first),
            descending severity, then medication name.
        """
        organ_eligible = egfr is not None or hepatic_function is not None
        if not organ_eligible and not breastfeeding:
            logger.info("renal_hepatic_lactation_checked", findings=0, eligible=False)
            return []

        organ_by_medication = (
            self._organ_findings(
                medications=medications,
                egfr=egfr,
                hepatic_function=hepatic_function,
            )
            if organ_eligible
            else {}
        )
        lactation_findings = (
            self._lactation_checker.check(medications=medications, breastfeeding=True)
            if breastfeeding
            else []
        )
        lactation_by_medication = {finding.medication: finding for finding in lactation_findings}

        all_medications = sorted(
            set(organ_by_medication) | set(lactation_by_medication),
            key=str.casefold,
        )

        findings: list[RenalHepaticLactationRisk] = []
        for medication in all_medications:
            organ = organ_by_medication.get(medication)
            lactation = lactation_by_medication.get(medication)

            if organ is not None and lactation is not None and breastfeeding:
                findings.append(self._build_combined(organ, lactation))
            elif organ is not None:
                findings.append(self._build_organ_only(organ))
            elif lactation is not None:
                findings.append(self._build_lactation_only(lactation))

        findings.sort(
            key=lambda finding: (
                -_CONCERN_KIND_RANK[finding.concern_kind],
                -_SEVERITY_RANK[finding.severity],
                finding.medication.casefold(),
                finding.agent.casefold(),
            )
        )
        logger.info(
            "renal_hepatic_lactation_checked",
            findings=len(findings),
            eligible=True,
            breastfeeding=breastfeeding,
            organ_eligible=organ_eligible,
        )
        return findings

    def _organ_findings(
        self,
        medications: list[Medication],
        egfr: float | None,
        hepatic_function: HepaticFunction | None,
    ) -> dict[str, _OrganFinding]:
        """Merge renal and hepatic findings keyed by medication display name."""
        renal_findings = (
            self._renal_checker.check(medications=medications, egfr=egfr)
            if egfr is not None
            else []
        )
        hepatic_findings = (
            self._hepatic_checker.check(
                medications=medications,
                hepatic_function=hepatic_function,
            )
            if hepatic_function is not None
            else []
        )

        renal_by_medication = {finding.medication: finding for finding in renal_findings}
        hepatic_by_medication = {finding.medication: finding for finding in hepatic_findings}

        merged: dict[str, _OrganFinding] = {}
        for medication in set(renal_by_medication) | set(hepatic_by_medication):
            renal = renal_by_medication.get(medication)
            hepatic = hepatic_by_medication.get(medication)
            agent = self._organ_agent(renal, hepatic)
            severity = self._organ_severity(renal, hepatic)
            merged[medication] = _OrganFinding(
                medication=medication,
                agent=agent,
                renal=renal,
                hepatic=hepatic,
                severity=severity,
            )
        return merged

    @staticmethod
    def _organ_agent(
        renal: RenalDoseRisk | None,
        hepatic: HepaticDoseRisk | None,
    ) -> str:
        """Choose a stable reporting agent for organ-impairment findings."""
        if renal is not None and hepatic is not None:
            if renal.agent == hepatic.agent:
                return renal.agent
            if _SEVERITY_RANK[renal.severity] >= _SEVERITY_RANK[hepatic.severity]:
                return renal.agent
            return hepatic.agent
        if renal is not None:
            return renal.agent
        assert hepatic is not None
        return hepatic.agent

    @staticmethod
    def _organ_severity(
        renal: RenalDoseRisk | None,
        hepatic: HepaticDoseRisk | None,
    ) -> Severity:
        """Return the maximum severity across organ components that fired."""
        if renal is not None and hepatic is not None:
            return RenalHepaticLactationChecker._max_severity(renal.severity, hepatic.severity)
        if renal is not None:
            return renal.severity
        assert hepatic is not None
        return hepatic.severity

    @staticmethod
    def _build_combined(
        organ: _OrganFinding,
        lactation: LactationRisk,
    ) -> RenalHepaticLactationRisk:
        """Compose a dual organ + lactation finding with escalated severity."""
        component_max = RenalHepaticLactationChecker._max_severity(
            organ.severity, lactation.severity
        )
        severity = _COMBINED_ESCALATION[component_max]
        agent = organ.agent if organ.agent == lactation.agent else lactation.agent
        organ_bits = RenalHepaticLactationChecker._organ_rationale_bits(organ)
        rationale = (
            "RESEARCH USE ONLY: "
            f"Medication '{organ.medication}' matches both organ-impairment and lactation "
            f"safety concerns. Organ component: {organ.agent} ({organ.severity.value})"
            f"{organ_bits}. Lactation component: {lactation.agent} "
            f"({lactation.severity.value}, {lactation.concern_category}) — "
            f"{lactation.rationale} Dual organ-function and breastfeeding exposure warrants "
            "heightened review before any medication change."
        )
        return RenalHepaticLactationRisk(
            medication=organ.medication,
            agent=agent,
            concern_kind=RenalHepaticLactationConcernKind.COMBINED,
            egfr=organ.renal.egfr if organ.renal is not None else None,
            threshold_egfr=organ.renal.threshold_egfr if organ.renal is not None else None,
            hepatic_function=(
                organ.hepatic.hepatic_function if organ.hepatic is not None else None
            ),
            threshold_function=(
                organ.hepatic.threshold_function if organ.hepatic is not None else None
            ),
            renal_action=organ.renal.action if organ.renal is not None else None,
            hepatic_action=organ.hepatic.action if organ.hepatic is not None else None,
            renal_severity=organ.renal.severity if organ.renal is not None else None,
            hepatic_severity=organ.hepatic.severity if organ.hepatic is not None else None,
            organ_severity=organ.severity,
            lactation_severity=lactation.severity,
            lactation_concern_category=lactation.concern_category,
            severity=severity,
            rationale=rationale,
        )

    @staticmethod
    def _build_organ_only(organ: _OrganFinding) -> RenalHepaticLactationRisk:
        """Compose an organ-impairment-only finding."""
        organ_bits = RenalHepaticLactationChecker._organ_rationale_bits(organ)
        return RenalHepaticLactationRisk(
            medication=organ.medication,
            agent=organ.agent,
            concern_kind=RenalHepaticLactationConcernKind.ORGAN_ONLY,
            egfr=organ.renal.egfr if organ.renal is not None else None,
            threshold_egfr=organ.renal.threshold_egfr if organ.renal is not None else None,
            hepatic_function=(
                organ.hepatic.hepatic_function if organ.hepatic is not None else None
            ),
            threshold_function=(
                organ.hepatic.threshold_function if organ.hepatic is not None else None
            ),
            renal_action=organ.renal.action if organ.renal is not None else None,
            hepatic_action=organ.hepatic.action if organ.hepatic is not None else None,
            renal_severity=organ.renal.severity if organ.renal is not None else None,
            hepatic_severity=organ.hepatic.severity if organ.hepatic is not None else None,
            organ_severity=organ.severity,
            lactation_severity=None,
            lactation_concern_category=None,
            severity=organ.severity,
            rationale=(
                "RESEARCH USE ONLY: "
                f"Organ-impairment-only concern for '{organ.medication}' "
                f"({organ.agent}, {organ.severity.value}){organ_bits}."
            ),
        )

    @staticmethod
    def _build_lactation_only(lactation: LactationRisk) -> RenalHepaticLactationRisk:
        """Compose a lactation-only finding."""
        return RenalHepaticLactationRisk(
            medication=lactation.medication,
            agent=lactation.agent,
            concern_kind=RenalHepaticLactationConcernKind.LACTATION_ONLY,
            egfr=None,
            threshold_egfr=None,
            hepatic_function=None,
            threshold_function=None,
            renal_action=None,
            hepatic_action=None,
            renal_severity=None,
            hepatic_severity=None,
            organ_severity=None,
            lactation_severity=lactation.severity,
            lactation_concern_category=lactation.concern_category,
            severity=lactation.severity,
            rationale=(
                "RESEARCH USE ONLY: "
                f"Lactation-only concern for '{lactation.medication}': {lactation.rationale}"
            ),
        )

    @staticmethod
    def _organ_rationale_bits(organ: _OrganFinding) -> str:
        """Format optional renal/hepatic detail fragments for rationales."""
        bits: list[str] = []
        if organ.renal is not None:
            bits.append(
                f"renal eGFR {organ.renal.egfr:g} at/below {organ.renal.threshold_egfr:g}, "
                f"action {organ.renal.action}"
            )
        if organ.hepatic is not None:
            bits.append(
                f"hepatic {organ.hepatic.hepatic_function.value} at/above "
                f"{organ.hepatic.threshold_function.value}, action {organ.hepatic.action}"
            )
        if not bits:
            return ""
        return " — " + "; ".join(bits)

    @staticmethod
    def _max_severity(first: Severity, second: Severity) -> Severity:
        """Return the higher-ranked severity."""
        if _SEVERITY_RANK[first] >= _SEVERITY_RANK[second]:
            return first
        return second
