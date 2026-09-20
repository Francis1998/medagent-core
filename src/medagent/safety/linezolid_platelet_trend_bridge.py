"""Linezolid + serial platelet count declining/low trend bridge.

Existing LinezolidSsriChecker covers SSRI serotonin-syndrome pairs without
serial platelet trends, and LabTrendAlertBridge is drug-agnostic — neither
maps linezolid exposure onto declining or low serial platelet counts.

This bridge fills that gap: it combines linezolid exposure with declining or
low serial platelet values into myelosuppression advisory
:class:`~medagent.models.LinezolidPlateletTrendAlert` findings.
RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import LinezolidPlateletTrendAlert, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_LINEZOLID_AGENTS: Final[frozenset[str]] = frozenset(
    {
        "linezolid",
        "zyvox",
    }
)

_PLATELET_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "platelet",
        "platelet count",
        "platelets",
        "plt",
        "thrombocyte count",
    }
)

# Advisory platelet thresholds (cells/uL) — RESEARCH USE ONLY, not dosing guidance.
_LOW_PLATELET: Final[float] = 100000.0
_CRITICAL_PLATELET: Final[float] = 50000.0
_MIN_RELATIVE_DECLINE: Final[float] = 0.2


class LinezolidPlateletTrendBridge:
    """Map linezolid exposure + serial platelet trends to thrombocytopenia cues."""

    def check(
        self,
        medications: list[Medication],
        labs: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[LinezolidPlateletTrendAlert]:
        """Return linezolid + platelet-trend thrombocytopenia advisories.

        Args:
            medications: Active medications.
            labs: Optional serial draws with ``name``, ``value``, optional
                ``unit`` / ``drawn_at`` (platelet).

        Returns:
            Zero or more :class:`LinezolidPlateletTrendAlert` findings. Distinct from
            :class:`LinezolidSsriChecker` and :class:`LabTrendAlertBridge`.
            Never modifies medications.
        """
        matched: list[tuple[str, str]] = []
        seen: set[str] = set()
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _LINEZOLID_AGENTS):
                if agent in seen:
                    continue
                matched.append((medication.name, agent))
                seen.add(agent)

        agents = [agent for _med, agent in matched]
        med_names = sorted({med for med, _agent in matched}, key=str.casefold)

        series: list[tuple[str, float]] = []
        for entry in labs or []:
            name = str(entry.get("name", "")).strip().lower()
            if name not in _PLATELET_ALIASES and "platelet" not in name and name != "platelet":
                continue
            try:
                value = float(entry.get("value"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            drawn = str(entry.get("drawn_at") or "")
            series.append((drawn, value))

        series.sort(key=lambda item: item[0])
        values = [value for _drawn, value in series]
        drawn_ats = [drawn for drawn, _value in series]
        latest = values[-1] if values else None
        percent: float | None = None
        if len(values) >= 2 and values[0] != 0:
            percent = (values[-1] - values[0]) / values[0] * 100.0

        if not agents:
            logger.info("linezolid_platelet_trend_bridge_checked", findings=0)
            return []

        findings: list[LinezolidPlateletTrendAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                LinezolidPlateletTrendAlert(
                    finding_kind=kind,
                    agents=agents,
                    medication_names=med_names,
                    platelet_values=values,
                    drawn_ats=drawn_ats,
                    latest_platelet=latest,
                    percent_change=percent,
                    severity=severity,
                    rationale=rationale,
                )
            )

        declining = len(values) >= 2 and values[-1] < values[0]
        significant_decline = percent is not None and percent <= -_MIN_RELATIVE_DECLINE * 100.0
        low = latest is not None and latest < _LOW_PLATELET
        critical = latest is not None and latest < _CRITICAL_PLATELET

        if (significant_decline or (declining and low)) and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            _add(
                "declining_platelet_on_linezolid",
                sev,
                (
                    "RESEARCH USE ONLY: Declining platelet trend on linezolid "
                    f"(values {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + f"). Agents: {', '.join(agents)}. myelosuppression platelet-trend "
                    "bridge distinct from LinezolidSsriChecker single-threshold "
                    "reminders and LabTrendAlertBridge DDI pairs. Never "
                    "modifies medications. Confirm with a qualified clinician; "
                    "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if low and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            kind = (
                "critical_low_platelets_on_linezolid"
                if critical
                else "low_platelets_on_linezolid"
            )
            _add(
                kind,
                sev,
                (
                    "RESEARCH USE ONLY: "
                    + ("Critical low" if critical else "Low")
                    + f" platelet on linezolid (latest {latest}, series {values}). "
                    f"Agents: {', '.join(agents)}. myelosuppression platelet-trend bridge "
                    "distinct from LinezolidSsriChecker and LabTrendAlertBridge. "
                    "Never modifies medications. Confirm with a qualified "
                    "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x "
                    "/ Kimi K2."
                ),
            )

        if (significant_decline or low) and agents:
            _add(
                "linezolid_platelet_rems_advisory",
                Severity.CRITICAL if critical else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Linezolid platelet myelosuppression advisory for "
                    f"agents {', '.join(agents)} (platelet {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + "). Distinct from LinezolidSsriChecker single-threshold "
                    "monitoring cues and LabTrendAlertBridge CYP1A2 pairs. "
                    "Never modifies medications. Confirm with a qualified "
                    "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini "
                    "3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("linezolid_platelet_trend_bridge_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
