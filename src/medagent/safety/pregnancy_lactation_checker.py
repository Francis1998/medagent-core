"""Combined pregnancy + lactation medication-safety checker.

Patients who are pregnant, breastfeeding, or both may need a unified view of
fetal teratogenicity and infant milk-transfer hazards. The standalone pregnancy
and lactation checkers each gate on their own status flag; this checker composes
both and surfaces three finding kinds:

* **combined** — the same medication triggers both pregnancy and lactation
  concerns (severity is escalated one rank, capped at ``CRITICAL``);
* **pregnancy_only** — teratogenic concern when ``pregnant=True``;
* **lactation_only** — breastfeeding concern when ``breastfeeding=True``.

The checker is deterministic, reuses the curated panels from
:class:`PregnancySafetyChecker` and :class:`LactationSafetyChecker`, and is
RESEARCH USE ONLY.
"""

from __future__ import annotations

from medagent.logging_config import get_logger
from medagent.models import (
    LactationRisk,
    Medication,
    PregnancyLactationConcernKind,
    PregnancyLactationRisk,
    PregnancyRisk,
    Severity,
)
from medagent.safety.lactation_checker import LactationSafetyChecker
from medagent.safety.pregnancy_checker import PregnancySafetyChecker

logger = get_logger(__name__)

# Higher rank = more severe, used for ordering and escalation.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_CONCERN_KIND_RANK: dict[PregnancyLactationConcernKind, int] = {
    PregnancyLactationConcernKind.COMBINED: 2,
    PregnancyLactationConcernKind.PREGNANCY_ONLY: 1,
    PregnancyLactationConcernKind.LACTATION_ONLY: 0,
}

# Escalate combined findings one severity rank above the component maximum.
_COMBINED_ESCALATION: dict[Severity, Severity] = {
    Severity.UNKNOWN: Severity.LOW,
    Severity.LOW: Severity.MODERATE,
    Severity.MODERATE: Severity.HIGH,
    Severity.HIGH: Severity.CRITICAL,
    Severity.CRITICAL: Severity.CRITICAL,
}


class PregnancyLactationChecker:
    """Flag medications with pregnancy, lactation, or dual reproductive concerns."""

    def __init__(
        self,
        pregnancy_checker: PregnancySafetyChecker | None = None,
        lactation_checker: LactationSafetyChecker | None = None,
    ) -> None:
        """Initialize the combined checker.

        Args:
            pregnancy_checker: Optional pregnancy checker dependency for tests or
                alternate curated panels.
            lactation_checker: Optional lactation checker dependency for tests or
                alternate curated panels.
        """
        self._pregnancy_checker = pregnancy_checker or PregnancySafetyChecker()
        self._lactation_checker = lactation_checker or LactationSafetyChecker()

    def check(
        self,
        medications: list[Medication],
        pregnant: bool,
        breastfeeding: bool,
    ) -> list[PregnancyLactationRisk]:
        """Return unified pregnancy and/or lactation safety findings.

        Args:
            medications: Active patient medications.
            pregnant: Whether the patient is documented as pregnant.
            breastfeeding: Whether the patient is documented as breastfeeding /
                lactating.

        Returns:
            One :class:`PregnancyLactationRisk` per flagged medication. Combined
            findings are emitted only when both status flags are true and the
            same medication appears in both component findings. Findings are
            ordered by concern kind (combined first), descending severity, then
            medication name.
        """
        if not pregnant and not breastfeeding:
            logger.info("pregnancy_lactation_checked", findings=0, eligible=False)
            return []

        pregnancy_findings = (
            self._pregnancy_checker.check(medications=medications, pregnant=True)
            if pregnant
            else []
        )
        lactation_findings = (
            self._lactation_checker.check(medications=medications, breastfeeding=True)
            if breastfeeding
            else []
        )

        pregnancy_by_medication = {finding.medication: finding for finding in pregnancy_findings}
        lactation_by_medication = {finding.medication: finding for finding in lactation_findings}

        all_medications = sorted(
            set(pregnancy_by_medication) | set(lactation_by_medication),
            key=str.casefold,
        )

        findings: list[PregnancyLactationRisk] = []
        for medication in all_medications:
            pregnancy = pregnancy_by_medication.get(medication)
            lactation = lactation_by_medication.get(medication)

            if pregnancy is not None and lactation is not None and pregnant and breastfeeding:
                findings.append(self._build_combined(medication, pregnancy, lactation))
            elif pregnancy is not None:
                findings.append(self._build_pregnancy_only(pregnancy))
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
            "pregnancy_lactation_checked",
            findings=len(findings),
            eligible=True,
            pregnant=pregnant,
            breastfeeding=breastfeeding,
        )
        return findings

    @staticmethod
    def _build_combined(
        medication: str,
        pregnancy: PregnancyRisk,
        lactation: LactationRisk,
    ) -> PregnancyLactationRisk:
        """Compose a dual pregnancy + lactation finding with escalated severity."""
        component_max = PregnancyLactationChecker._max_severity(
            pregnancy.severity, lactation.severity
        )
        severity = _COMBINED_ESCALATION[component_max]
        agent = pregnancy.agent
        rationale = (
            "RESEARCH USE ONLY: "
            f"Medication '{medication}' matches both pregnancy and lactation safety concerns. "
            f"Pregnancy component: {pregnancy.agent} ({pregnancy.severity.value}) — "
            f"{pregnancy.rationale} Lactation component: {lactation.agent} "
            f"({lactation.severity.value}, {lactation.concern_category}) — "
            f"{lactation.rationale} Dual reproductive exposure warrants heightened review "
            "before any medication change."
        )
        return PregnancyLactationRisk(
            medication=medication,
            agent=agent,
            concern_kind=PregnancyLactationConcernKind.COMBINED,
            pregnancy_severity=pregnancy.severity,
            lactation_severity=lactation.severity,
            lactation_concern_category=lactation.concern_category,
            severity=severity,
            rationale=rationale,
        )

    @staticmethod
    def _build_pregnancy_only(pregnancy: PregnancyRisk) -> PregnancyLactationRisk:
        """Compose a pregnancy-only finding."""
        return PregnancyLactationRisk(
            medication=pregnancy.medication,
            agent=pregnancy.agent,
            concern_kind=PregnancyLactationConcernKind.PREGNANCY_ONLY,
            pregnancy_severity=pregnancy.severity,
            lactation_severity=None,
            lactation_concern_category=None,
            severity=pregnancy.severity,
            rationale=(
                "RESEARCH USE ONLY: "
                f"Pregnancy-only concern for '{pregnancy.medication}': {pregnancy.rationale}"
            ),
        )

    @staticmethod
    def _build_lactation_only(lactation: LactationRisk) -> PregnancyLactationRisk:
        """Compose a lactation-only finding."""
        return PregnancyLactationRisk(
            medication=lactation.medication,
            agent=lactation.agent,
            concern_kind=PregnancyLactationConcernKind.LACTATION_ONLY,
            pregnancy_severity=None,
            lactation_severity=lactation.severity,
            lactation_concern_category=lactation.concern_category,
            severity=lactation.severity,
            rationale=(
                "RESEARCH USE ONLY: "
                f"Lactation-only concern for '{lactation.medication}': {lactation.rationale}"
            ),
        )

    @staticmethod
    def _max_severity(first: Severity, second: Severity) -> Severity:
        """Return the higher-ranked severity."""
        if _SEVERITY_RANK[first] >= _SEVERITY_RANK[second]:
            return first
        return second
