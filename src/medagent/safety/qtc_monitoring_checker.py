"""QTc ECG monitoring-interval safety checker.

Clinical decision support for QT-prolonging drugs often recommends periodic ECG
monitoring — especially at initiation and after dose changes — to detect
clinically significant QT prolongation before torsades de pointes. The existing
:mod:`qt_prolongation_checker` and :mod:`qtc_ddi_checker` identify QT-prolonging
agents and synergistic pairs; this checker focuses on whether the documented
ECG monitoring cadence is adequate for high-risk agents.

It flags high-risk QT-prolonging medications when the last ECG is missing or
older than the recommended initiation (default 7 days) or maintenance (default
30 days) interval. Whole-token matching avoids substring false positives.
Findings are deterministic, RESEARCH USE ONLY, and standalone.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, QtcMonitoringRisk, Severity

logger = get_logger(__name__)

# Recommended ECG monitoring intervals (days) for high-risk QT agents.
_INITIATION_INTERVAL_DAYS: Final[int] = 7
_MAINTENANCE_INTERVAL_DAYS: Final[int] = 30

# Prolonged baseline QTc (ms) that warrants heightened concern in the rationale.
_PROLONGED_QTC_MS: Final[float] = 500.0
_BORDERLINE_QTC_MS: Final[float] = 480.0

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical high-risk QT agent token -> (risk_category, baseline severity).
# These agents always require periodic ECG monitoring when active.
_QTC_MONITORING_AGENTS: dict[str, tuple[str, Severity]] = {
    "dofetilide": ("class III antiarrhythmic", Severity.CRITICAL),
    "sotalol": ("class III antiarrhythmic", Severity.CRITICAL),
    "amiodarone": ("class III antiarrhythmic", Severity.HIGH),
    "methadone": ("opioid", Severity.HIGH),
    "haloperidol": ("antipsychotic", Severity.HIGH),
    "ziprasidone": ("antipsychotic", Severity.HIGH),
    "quinidine": ("class Ia antiarrhythmic", Severity.CRITICAL),
    "procainamide": ("class Ia antiarrhythmic", Severity.HIGH),
    "thioridazine": ("antipsychotic", Severity.HIGH),
}

# Dose thresholds for agents where only higher exposures warrant monitoring.
_CITALOPRAM_HIGH_DOSE_MG: Final[float] = 40.0
_ESCITALOPRAM_HIGH_DOSE_MG: Final[float] = 20.0


class QtcMonitoringChecker:
    """Flag inadequate ECG monitoring intervals for high-risk QT-prolonging drugs."""

    def check(
        self,
        medications: list[Medication],
        last_ecg_days_ago: int | None = None,
        baseline_qtc_ms: float | None = None,
        *,
        on_initiation: bool = False,
    ) -> list[QtcMonitoringRisk]:
        """Return findings when ECG monitoring is missing or overdue.

        Args:
            medications: Active patient medications.
            last_ecg_days_ago: Days since the most recent ECG, or None when
                unknown/missing. A missing value always triggers a finding for
                each matching high-risk agent.
            baseline_qtc_ms: Most recent documented QTc in milliseconds, if
                known. Values ≥480 ms are noted in the rationale; values
                ≥500 ms elevate severity for non-CRITICAL findings.
            on_initiation: When True, apply the stricter initiation interval
                (7 days). When False, apply the maintenance interval (30 days).

        Returns:
            One :class:`QtcMonitoringRisk` per matching medication with
            inadequate monitoring, ordered by descending severity then medication
            name.
        """
        recommended_interval = (
            _INITIATION_INTERVAL_DAYS if on_initiation else _MAINTENANCE_INTERVAL_DAYS
        )
        monitoring_phase = "initiation" if on_initiation else "maintenance"
        ecg_overdue = last_ecg_days_ago is None or last_ecg_days_ago > recommended_interval

        findings: list[QtcMonitoringRisk] = []
        for medication in medications:
            match = self._match_monitoring_agent(medication.name)
            if match is None:
                continue
            agent, risk_category, severity = match
            if not ecg_overdue:
                continue

            effective_severity = self._effective_severity(severity, baseline_qtc_ms)
            findings.append(
                QtcMonitoringRisk(
                    medication=medication.name,
                    agent=agent,
                    risk_category=risk_category,
                    severity=effective_severity,
                    last_ecg_days_ago=last_ecg_days_ago,
                    recommended_interval_days=recommended_interval,
                    monitoring_phase=monitoring_phase,
                    baseline_qtc_ms=baseline_qtc_ms,
                    rationale=self._build_rationale(
                        medication_name=medication.name,
                        agent=agent,
                        risk_category=risk_category,
                        last_ecg_days_ago=last_ecg_days_ago,
                        recommended_interval=recommended_interval,
                        monitoring_phase=monitoring_phase,
                        baseline_qtc_ms=baseline_qtc_ms,
                    ),
                )
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.medication))
        logger.info("qtc_monitoring_checked", findings=len(findings), overdue=ecg_overdue)
        return findings

    def _match_monitoring_agent(self, medication_name: str) -> tuple[str, str, Severity] | None:
        """Return the matched agent, category, and severity for a medication name."""
        tokens = self._tokens(medication_name)
        if not tokens:
            return None

        matched_agents = sorted(tokens & set(_QTC_MONITORING_AGENTS))
        if matched_agents:
            agent = matched_agents[0]
            risk_category, severity = _QTC_MONITORING_AGENTS[agent]
            return agent, risk_category, severity

        if "citalopram" in tokens and self._dose_exceeds(medication_name, _CITALOPRAM_HIGH_DOSE_MG):
            return (
                "citalopram",
                "SSRI (high dose)",
                Severity.HIGH,
            )
        if "escitalopram" in tokens and self._dose_exceeds(
            medication_name, _ESCITALOPRAM_HIGH_DOSE_MG
        ):
            return (
                "escitalopram",
                "SSRI (high dose)",
                Severity.HIGH,
            )
        if self._is_ondansetron_iv(medication_name, tokens):
            return (
                "ondansetron",
                "antiemetic (IV)",
                Severity.HIGH,
            )
        return None

    @staticmethod
    def _effective_severity(baseline_severity: Severity, baseline_qtc_ms: float | None) -> Severity:
        """Elevate severity when baseline QTc is markedly prolonged."""
        if baseline_qtc_ms is None or baseline_qtc_ms < _PROLONGED_QTC_MS:
            return baseline_severity
        if baseline_severity is Severity.CRITICAL:
            return Severity.CRITICAL
        return Severity.CRITICAL

    @staticmethod
    def _build_rationale(
        *,
        medication_name: str,
        agent: str,
        risk_category: str,
        last_ecg_days_ago: int | None,
        recommended_interval: int,
        monitoring_phase: str,
        baseline_qtc_ms: float | None,
    ) -> str:
        """Compose a RESEARCH USE ONLY monitoring-interval rationale."""
        if last_ecg_days_ago is None:
            ecg_status = "no recent ECG is documented"
        else:
            ecg_status = (
                f"the last ECG was {last_ecg_days_ago} day(s) ago "
                f"(>{recommended_interval}-day {monitoring_phase} interval)"
            )

        qtc_note = ""
        if baseline_qtc_ms is not None:
            if baseline_qtc_ms >= _PROLONGED_QTC_MS:
                qtc_note = (
                    f" Documented baseline QTc {baseline_qtc_ms:.0f} ms is prolonged "
                    f"(≥{_PROLONGED_QTC_MS:.0f} ms) — prioritize urgent ECG review."
                )
            elif baseline_qtc_ms >= _BORDERLINE_QTC_MS:
                qtc_note = (
                    f" Documented baseline QTc {baseline_qtc_ms:.0f} ms is borderline "
                    f"(≥{_BORDERLINE_QTC_MS:.0f} ms) — consider closer monitoring."
                )

        return (
            "RESEARCH USE ONLY: "
            f"Medication '{medication_name}' contains {agent}, a {risk_category} "
            "with high torsades risk that warrants periodic ECG/QTc monitoring; "
            f"{ecg_status}. Recommended {monitoring_phase} ECG interval: "
            f"≤{recommended_interval} days.{qtc_note} Obtain or review an ECG "
            "and electrolytes with a qualified clinician before dose changes."
        )

    @staticmethod
    def _dose_exceeds(medication_name: str, threshold_mg: float) -> bool:
        """Return True when a mg dose in the name exceeds the threshold."""
        match = re.search(r"(\d+(?:\.\d+)?)\s*mg", medication_name.lower())
        if match is None:
            return False
        return float(match.group(1)) > threshold_mg

    @staticmethod
    def _is_ondansetron_iv(medication_name: str, tokens: set[str]) -> bool:
        """Return True for IV/injection ondansetron formulations."""
        if "ondansetron" not in tokens:
            return False
        lower = medication_name.lower()
        return "iv" in tokens or "intravenous" in lower or "injection" in lower

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
