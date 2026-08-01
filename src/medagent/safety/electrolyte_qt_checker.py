"""Electrolyte panel (K/Mg) with QT-prolonging drug safety checker.

Hypokalemia and hypomagnesemia increase the risk of QT prolongation and
torsades de pointes, especially when combined with QT-prolonging medications.
The existing QT-prolongation and QTc monitoring checkers flag QT drugs and
monitoring cadence; this checker complements them by evaluating potassium and
magnesium laboratory values against QT-prolonging agents on the medication list.

It flags QT-prolonging medications when potassium or magnesium labs are missing
or below conservative thresholds (K < 3.5 mmol/L, Mg < 1.7 mg/dL). Whole-token
matching is used throughout. Findings are deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import ElectrolyteQtRisk, Medication, Severity

logger = get_logger(__name__)

_POTASSIUM_LOW_THRESHOLD_MMOL_L: Final[float] = 3.5
_MAGNESIUM_LOW_THRESHOLD_MG_DL: Final[float] = 1.7

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_FINDING_KIND_RANK: Final[dict[str, int]] = {
    "low_potassium": 0,
    "low_magnesium": 1,
    "missing_electrolytes": 2,
}

# Canonical QT-prolonging agent -> short descriptor.
_QT_PROLONGING_AGENTS: Final[dict[str, str]] = {
    "methadone": "an opioid with QT-prolonging activity",
    "ondansetron": "a 5-HT3 antagonist antiemetic with QT-prolonging activity",
    "azithromycin": "a macrolide antibiotic with QT-prolonging activity",
    "amiodarone": "a class III antiarrhythmic with marked QT prolongation",
    "haloperidol": "a typical antipsychotic with QT-prolonging activity",
    "citalopram": "an SSRI with dose-dependent QT prolongation",
    "escitalopram": "an SSRI with dose-dependent QT prolongation",
    "sotalol": "a class III antiarrhythmic with QT prolongation",
    "dofetilide": "a class III antiarrhythmic with marked QT prolongation",
}


class ElectrolyteQtChecker:
    """Flag QT-prolonging medications when potassium or magnesium is missing or low."""

    def check(
        self,
        medications: list[Medication],
        potassium_mmol_l: float | None = None,
        magnesium_mg_dl: float | None = None,
    ) -> list[ElectrolyteQtRisk]:
        """Return findings for QT drugs with inadequate electrolyte status.

        Args:
            medications: Active patient medications.
            potassium_mmol_l: Serum potassium in mmol/L, or None when unknown.
            magnesium_mg_dl: Serum magnesium in mg/dL, or None when unknown.

        Returns:
            One :class:`ElectrolyteQtRisk` per QT-prolonging medication per
            applicable finding kind, ordered by descending severity then
            medication name and finding kind. An empty list is returned when no
            QT-prolonging agent is present or electrolytes are adequate.
        """
        qt_matches: list[tuple[Medication, str]] = []
        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue
            candidates = sorted(tokens & set(_QT_PROLONGING_AGENTS))
            if candidates:
                qt_matches.append((medication, candidates[0]))

        if not qt_matches:
            logger.info("electrolyte_qt_checked", findings=0)
            return []

        finding_kinds = self._electrolyte_finding_kinds(
            potassium_mmol_l=potassium_mmol_l,
            magnesium_mg_dl=magnesium_mg_dl,
        )
        if not finding_kinds:
            logger.info("electrolyte_qt_checked", findings=0, qt_agents=len(qt_matches))
            return []

        findings: list[ElectrolyteQtRisk] = []
        for medication, agent in qt_matches:
            descriptor = _QT_PROLONGING_AGENTS[agent]
            for finding_kind in finding_kinds:
                findings.append(
                    ElectrolyteQtRisk(
                        medication=medication.name,
                        agent=agent,
                        finding_kind=finding_kind,
                        severity=self._severity_for_kind(finding_kind),
                        potassium_mmol_l=potassium_mmol_l,
                        magnesium_mg_dl=magnesium_mg_dl,
                        rationale=self._build_rationale(
                            medication_name=medication.name,
                            agent=agent,
                            descriptor=descriptor,
                            finding_kind=finding_kind,
                            potassium_mmol_l=potassium_mmol_l,
                            magnesium_mg_dl=magnesium_mg_dl,
                        ),
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
            "electrolyte_qt_checked",
            findings=len(findings),
            qt_agents=len({agent for _med, agent in qt_matches}),
            finding_kinds=finding_kinds,
        )
        return findings

    @staticmethod
    def _electrolyte_finding_kinds(
        *,
        potassium_mmol_l: float | None,
        magnesium_mg_dl: float | None,
    ) -> list[str]:
        """Return applicable finding kinds for the supplied electrolyte values."""
        kinds: list[str] = []
        if potassium_mmol_l is None or magnesium_mg_dl is None:
            kinds.append("missing_electrolytes")
        if potassium_mmol_l is not None and potassium_mmol_l < _POTASSIUM_LOW_THRESHOLD_MMOL_L:
            kinds.append("low_potassium")
        if magnesium_mg_dl is not None and magnesium_mg_dl < _MAGNESIUM_LOW_THRESHOLD_MG_DL:
            kinds.append("low_magnesium")
        return kinds

    @staticmethod
    def _severity_for_kind(finding_kind: str) -> Severity:
        """Map finding kind to advisory severity."""
        if finding_kind in {"low_potassium", "low_magnesium"}:
            return Severity.HIGH
        return Severity.MODERATE

    @staticmethod
    def _build_rationale(
        *,
        medication_name: str,
        agent: str,
        descriptor: str,
        finding_kind: str,
        potassium_mmol_l: float | None,
        magnesium_mg_dl: float | None,
    ) -> str:
        """Compose a RESEARCH USE ONLY electrolyte × QT rationale."""
        if finding_kind == "missing_electrolytes":
            electrolyte_detail = "potassium and/or magnesium laboratory values are not documented"
        elif finding_kind == "low_potassium":
            electrolyte_detail = (
                f"potassium is low at {potassium_mmol_l:.1f} mmol/L "
                f"(threshold < {_POTASSIUM_LOW_THRESHOLD_MMOL_L:.1f} mmol/L)"
            )
        else:
            electrolyte_detail = (
                f"magnesium is low at {magnesium_mg_dl:.2f} mg/dL "
                f"(threshold < {_MAGNESIUM_LOW_THRESHOLD_MG_DL:.1f} mg/dL)"
            )
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{medication_name}' contains {agent}, {descriptor}. "
            f"Concurrent electrolyte status is concerning because {electrolyte_detail}. "
            "Hypokalemia and hypomagnesemia increase the risk of QT prolongation and "
            "torsades de pointes with QT-prolonging drugs. Review electrolytes urgently, "
            "correct deficiencies, and reassess QT risk before continuing therapy."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
