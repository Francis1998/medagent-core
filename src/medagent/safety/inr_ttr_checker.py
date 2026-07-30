"""Anticoagulation INR / TTR monitoring-cadence safety checker.

Vitamin K antagonist (VKA) therapy — principally warfarin — requires periodic
INR surveillance to keep anticoagulation in the therapeutic window. Clinics also
track time in therapeutic range (TTR) as a quality metric for dosing control.
The existing anticoagulation bleeding-risk checker flags co-prescribed
hemorrhage augmenters, and the lab critical-value checker flags panic INR
values; this checker focuses on whether INR monitoring cadence and TTR are
adequate for active VKA therapy.

It flags warfarin/VKA medications when the last INR is missing or older than
the recommended initiation (default 7 days) or maintenance (default 28 days)
interval, and when documented TTR falls below a configurable threshold (default
65%). Whole-token matching avoids substring false positives. Findings are
deterministic, RESEARCH USE ONLY, and standalone.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import InrTtrRisk, Medication, Severity

logger = get_logger(__name__)

# Recommended INR monitoring intervals (days) for VKA therapy.
_INITIATION_INTERVAL_DAYS: Final[int] = 7
_MAINTENANCE_INTERVAL_DAYS: Final[int] = 28

# Default TTR quality threshold (percent). Values below this are suboptimal.
_DEFAULT_TTR_THRESHOLD_PERCENT: Final[float] = 65.0
# Markedly poor TTR elevates severity to CRITICAL.
_CRITICAL_TTR_PERCENT: Final[float] = 50.0

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical VKA token -> (risk_category, baseline overdue-INR severity).
_VKA_AGENTS: Final[dict[str, tuple[str, Severity]]] = {
    "warfarin": ("vitamin K antagonist", Severity.HIGH),
    "acenocoumarol": ("vitamin K antagonist", Severity.HIGH),
    "phenprocoumon": ("vitamin K antagonist", Severity.HIGH),
}

# Brand / synonym tokens that canonicalize to a panel VKA.
_VKA_ALIASES: Final[dict[str, str]] = {
    "coumadin": "warfarin",
    "jantoven": "warfarin",
}


class InrTtrChecker:
    """Flag overdue INR checks or suboptimal TTR for warfarin/VKA patients."""

    def check(
        self,
        medications: list[Medication],
        last_inr_days_ago: int | None = None,
        ttr_percent: float | None = None,
        *,
        on_initiation: bool = False,
        ttr_threshold_percent: float = _DEFAULT_TTR_THRESHOLD_PERCENT,
    ) -> list[InrTtrRisk]:
        """Return findings when INR monitoring is overdue or TTR is low.

        Args:
            medications: Active patient medications.
            last_inr_days_ago: Days since the most recent INR, or None when
                unknown/missing. A missing value always triggers an overdue-INR
                finding for each matching VKA.
            ttr_percent: Documented time in therapeutic range (0–100), if known.
                Values strictly below ``ttr_threshold_percent`` trigger a low-TTR
                finding. ``None`` does not imply low TTR.
            on_initiation: When True, apply the stricter initiation interval
                (7 days). When False, apply the maintenance interval (28 days).
            ttr_threshold_percent: TTR percentage below which a low-TTR finding
                is emitted (default 65%).

        Returns:
            One or more :class:`InrTtrRisk` records per matching VKA medication
            (``overdue_inr`` and/or ``low_ttr``), ordered by descending severity,
            finding kind, then medication name.
        """
        recommended_interval = (
            _INITIATION_INTERVAL_DAYS if on_initiation else _MAINTENANCE_INTERVAL_DAYS
        )
        monitoring_phase = "initiation" if on_initiation else "maintenance"
        inr_overdue = last_inr_days_ago is None or last_inr_days_ago > recommended_interval
        ttr_low = ttr_percent is not None and ttr_percent < ttr_threshold_percent

        findings: list[InrTtrRisk] = []
        for medication in medications:
            match = self._match_vka(medication.name)
            if match is None:
                continue
            agent, risk_category, baseline_severity = match

            if inr_overdue:
                overdue_severity = self._overdue_severity(baseline_severity, on_initiation)
                findings.append(
                    InrTtrRisk(
                        medication=medication.name,
                        agent=agent,
                        risk_category=risk_category,
                        finding_kind="overdue_inr",
                        severity=overdue_severity,
                        last_inr_days_ago=last_inr_days_ago,
                        recommended_interval_days=recommended_interval,
                        monitoring_phase=monitoring_phase,
                        ttr_percent=ttr_percent,
                        ttr_threshold_percent=ttr_threshold_percent,
                        rationale=self._build_overdue_rationale(
                            medication_name=medication.name,
                            agent=agent,
                            risk_category=risk_category,
                            last_inr_days_ago=last_inr_days_ago,
                            recommended_interval=recommended_interval,
                            monitoring_phase=monitoring_phase,
                        ),
                    )
                )

            if ttr_low and ttr_percent is not None:
                findings.append(
                    InrTtrRisk(
                        medication=medication.name,
                        agent=agent,
                        risk_category=risk_category,
                        finding_kind="low_ttr",
                        severity=self._ttr_severity(ttr_percent),
                        last_inr_days_ago=last_inr_days_ago,
                        recommended_interval_days=recommended_interval,
                        monitoring_phase=monitoring_phase,
                        ttr_percent=ttr_percent,
                        ttr_threshold_percent=ttr_threshold_percent,
                        rationale=self._build_ttr_rationale(
                            medication_name=medication.name,
                            agent=agent,
                            risk_category=risk_category,
                            ttr_percent=ttr_percent,
                            ttr_threshold_percent=ttr_threshold_percent,
                        ),
                    )
                )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.finding_kind,
                finding.medication,
            )
        )
        logger.info(
            "inr_ttr_checked",
            findings=len(findings),
            inr_overdue=inr_overdue,
            ttr_low=ttr_low,
        )
        return findings

    def _match_vka(self, medication_name: str) -> tuple[str, str, Severity] | None:
        """Return the matched canonical VKA, category, and baseline severity."""
        tokens = self._tokens(medication_name)
        if not tokens:
            return None

        canonical_agents: set[str] = set()
        for token in tokens:
            if token in _VKA_AGENTS:
                canonical_agents.add(token)
            elif token in _VKA_ALIASES:
                canonical_agents.add(_VKA_ALIASES[token])

        if not canonical_agents:
            return None

        agent = sorted(canonical_agents)[0]
        risk_category, severity = _VKA_AGENTS[agent]
        return agent, risk_category, severity

    @staticmethod
    def _overdue_severity(baseline_severity: Severity, on_initiation: bool) -> Severity:
        """Elevate missing/overdue INR severity during initiation."""
        if on_initiation:
            return Severity.CRITICAL
        return baseline_severity

    @staticmethod
    def _ttr_severity(ttr_percent: float) -> Severity:
        """Map TTR percentage to severity; markedly low TTR is CRITICAL."""
        if ttr_percent < _CRITICAL_TTR_PERCENT:
            return Severity.CRITICAL
        return Severity.HIGH

    @staticmethod
    def _build_overdue_rationale(
        *,
        medication_name: str,
        agent: str,
        risk_category: str,
        last_inr_days_ago: int | None,
        recommended_interval: int,
        monitoring_phase: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY overdue-INR rationale."""
        if last_inr_days_ago is None:
            inr_status = "no recent INR is documented"
        else:
            inr_status = (
                f"the last INR was {last_inr_days_ago} day(s) ago "
                f"(>{recommended_interval}-day {monitoring_phase} interval)"
            )

        return (
            "RESEARCH USE ONLY: "
            f"Medication '{medication_name}' contains {agent}, a {risk_category} "
            "that requires periodic INR monitoring to maintain therapeutic "
            f"anticoagulation; {inr_status}. Recommended {monitoring_phase} INR "
            f"interval: ≤{recommended_interval} days. Obtain or review an INR "
            "and dosing plan with a qualified clinician before dose changes."
        )

    @staticmethod
    def _build_ttr_rationale(
        *,
        medication_name: str,
        agent: str,
        risk_category: str,
        ttr_percent: float,
        ttr_threshold_percent: float,
    ) -> str:
        """Compose a RESEARCH USE ONLY low-TTR rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{medication_name}' contains {agent}, a {risk_category}; "
            f"documented time in therapeutic range (TTR) is {ttr_percent:.1f}% "
            f"(below the {ttr_threshold_percent:.0f}% quality threshold). Low TTR "
            "is associated with increased thromboembolic and bleeding events. "
            "Review adherence, interacting medications, diet, and INR cadence "
            "with a qualified clinician."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
