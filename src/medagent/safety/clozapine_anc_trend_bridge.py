"""Clozapine + serial ANC (absolute neutrophil count) declining/low trend bridge.

The existing
:class:`~medagent.safety.clozapine_anc_checker.ClozapineAncChecker` emits a
single-threshold ANC monitoring reminder whenever clozapine is present, and
:class:`~medagent.safety.clozapine_cyp1a2_checker.ClozapineCyp1a2Checker`
covers CYP1A2 interaction pairs — neither maps clozapine exposure onto
declining or low serial absolute neutrophil count trends.

This bridge fills that gap: it combines clozapine exposure with declining or
low serial ANC values into REMS-style advisory
:class:`~medagent.models.ClozapineAncTrendAlert` findings.
RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import ClozapineAncTrendAlert, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_CLOZAPINE_AGENTS: Final[frozenset[str]] = frozenset(
    {
        "clozapine",
        "clozaril",
        "fazaclo",
        "versacloz",
    }
)

_ANC_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "anc",
        "absolute neutrophil count",
        "neutrophil count",
        "absolute neutrophils",
        "neutrophils absolute",
    }
)

# Advisory ANC thresholds (cells/µL) — RESEARCH USE ONLY, not dosing guidance.
_LOW_ANC: Final[float] = 1500.0
_CRITICAL_ANC: Final[float] = 1000.0
_MIN_RELATIVE_DECLINE: Final[float] = 0.2


class ClozapineAncTrendBridge:
    """Map clozapine exposure + serial ANC trends to REMS-style neutropenia cues."""

    def check(
        self,
        medications: list[Medication],
        labs: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[ClozapineAncTrendAlert]:
        """Return clozapine + ANC-trend neutropenia advisories.

        Args:
            medications: Active medications.
            labs: Optional serial draws with ``name``, ``value``, optional
                ``unit`` / ``drawn_at`` (ANC).

        Returns:
            Zero or more :class:`ClozapineAncTrendAlert` findings. Distinct from
            :class:`ClozapineAncChecker` and :class:`ClozapineCyp1a2Checker`.
            Never modifies medications.
        """
        matched: list[tuple[str, str]] = []
        seen: set[str] = set()
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _CLOZAPINE_AGENTS):
                if agent in seen:
                    continue
                matched.append((medication.name, agent))
                seen.add(agent)

        agents = [agent for _med, agent in matched]
        med_names = sorted({med for med, _agent in matched}, key=str.casefold)

        series: list[tuple[str, float]] = []
        for entry in labs or []:
            name = str(entry.get("name", "")).strip().lower()
            if name not in _ANC_ALIASES and "neutrophil" not in name and name != "anc":
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
            logger.info("clozapine_anc_trend_bridge_checked", findings=0)
            return []

        findings: list[ClozapineAncTrendAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                ClozapineAncTrendAlert(
                    finding_kind=kind,
                    agents=agents,
                    medication_names=med_names,
                    anc_values=values,
                    drawn_ats=drawn_ats,
                    latest_anc=latest,
                    percent_change=percent,
                    severity=severity,
                    rationale=rationale,
                )
            )

        declining = len(values) >= 2 and values[-1] < values[0]
        significant_decline = percent is not None and percent <= -_MIN_RELATIVE_DECLINE * 100.0
        low = latest is not None and latest < _LOW_ANC
        critical = latest is not None and latest < _CRITICAL_ANC

        if (significant_decline or (declining and low)) and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            _add(
                "declining_anc_on_clozapine",
                sev,
                (
                    "RESEARCH USE ONLY: Declining ANC trend on clozapine "
                    f"(values {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + f"). Agents: {', '.join(agents)}. REMS-style ANC-trend "
                    "bridge distinct from ClozapineAncChecker single-threshold "
                    "reminders and ClozapineCyp1a2Checker DDI pairs. Never "
                    "modifies medications. Confirm with a qualified clinician; "
                    "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if low and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            kind = "critical_low_anc_on_clozapine" if critical else "low_anc_on_clozapine"
            _add(
                kind,
                sev,
                (
                    "RESEARCH USE ONLY: "
                    + ("Critical low" if critical else "Low")
                    + f" ANC on clozapine (latest {latest}, series {values}). "
                    f"Agents: {', '.join(agents)}. REMS-style ANC-trend bridge "
                    "distinct from ClozapineAncChecker and ClozapineCyp1a2Checker. "
                    "Never modifies medications. Confirm with a qualified "
                    "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x "
                    "/ Kimi K2."
                ),
            )

        if (significant_decline or low) and agents:
            _add(
                "clozapine_anc_rems_advisory",
                Severity.CRITICAL if critical else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Clozapine ANC REMS-style advisory for "
                    f"agents {', '.join(agents)} (ANC {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + "). Distinct from ClozapineAncChecker single-threshold "
                    "monitoring cues and ClozapineCyp1a2Checker CYP1A2 pairs. "
                    "Never modifies medications. Confirm with a qualified "
                    "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini "
                    "3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("clozapine_anc_trend_bridge_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
