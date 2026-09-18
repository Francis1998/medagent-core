"""Heparin / LMWH + serial anti-Xa level monitoring trend bridge.

The existing
:class:`~medagent.safety.heparin_platelet_trend_bridge.HeparinPlateletTrendBridge`
covers heparin/LMWH + falling platelet HIT-risk trends — not serial anti-Xa
level monitoring while on heparin-class anticoagulation.

This bridge fills that gap: it combines heparin / UFH / LMWH exposure with
rising, elevated, or clearly supratherapeutic serial anti-Xa levels into
advisory :class:`~medagent.models.HeparinAntiXaTrendAlert` findings.
RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import HeparinAntiXaTrendAlert, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_AGENT_CLASS: Final[dict[str, str]] = {
    "heparin": "ufh",
    "ufh": "ufh",
    "unfractionated": "ufh",
    "enoxaparin": "lmwh",
    "dalteparin": "lmwh",
    "tinzaparin": "lmwh",
    "nadroparin": "lmwh",
    "fondaparinux": "other",
}

_ANTIXA_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "anti-xa",
        "anti xa",
        "antixa",
        "anti-xa level",
        "anti xa level",
        "heparin anti-xa",
        "lmwh anti-xa",
        "anti-factor xa",
        "factor xa activity",
    }
)

# Advisory anti-Xa thresholds (IU/mL) — RESEARCH USE ONLY, not dosing guidance.
_ELEVATED_ANTIXA: Final[float] = 1.0
_SUPRATHERAPEUTIC_ANTIXA: Final[float] = 1.5
_SUBTHERAPEUTIC_ANTIXA: Final[float] = 0.3
_MIN_RELATIVE_RISE: Final[float] = 0.25


class HeparinAntiXaTrendBridge:
    """Map heparin/LMWH exposure + serial anti-Xa levels to monitoring advisories."""

    def check(
        self,
        medications: list[Medication],
        labs: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[HeparinAntiXaTrendAlert]:
        """Return heparin + anti-Xa-trend monitoring advisories.

        Args:
            medications: Active medications.
            labs: Optional serial draws with ``name``, ``value``, optional
                ``unit`` / ``drawn_at`` (anti-Xa).

        Returns:
            Zero or more :class:`HeparinAntiXaTrendAlert` findings. Distinct
            from :class:`HeparinPlateletTrendBridge`. Never modifies medications.
        """
        matched: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & set(_AGENT_CLASS)):
                if agent in seen:
                    continue
                matched.append((medication.name, agent, _AGENT_CLASS[agent]))
                seen.add(agent)

        agents = [agent for _med, agent, _cls in matched]
        classes = sorted({cls for _med, _agent, cls in matched})
        med_names = sorted({med for med, _agent, _cls in matched}, key=str.casefold)

        series: list[tuple[str, float]] = []
        for entry in labs or []:
            name = str(entry.get("name", "")).strip().lower()
            normalized = name.replace("_", " ").replace("-", " ")
            looks_like = (
                "anti xa" in normalized
                or "antixa" in normalized.replace(" ", "")
                or "factor xa" in normalized
            )
            if name not in _ANTIXA_ALIASES and not looks_like:
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
            logger.info("heparin_antixa_trend_bridge_checked", findings=0)
            return []

        findings: list[HeparinAntiXaTrendAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                HeparinAntiXaTrendAlert(
                    finding_kind=kind,
                    agents=agents,
                    agent_classes=classes,
                    medication_names=med_names,
                    antixa_values=values,
                    drawn_ats=drawn_ats,
                    latest_antixa=latest,
                    percent_change=percent,
                    severity=severity,
                    rationale=rationale,
                )
            )

        rising = len(values) >= 2 and values[-1] > values[0]
        significant_rise = percent is not None and percent >= _MIN_RELATIVE_RISE * 100.0
        elevated = latest is not None and latest >= _ELEVATED_ANTIXA
        critical = latest is not None and latest >= _SUPRATHERAPEUTIC_ANTIXA
        subtherapeutic = (
            latest is not None
            and latest < _SUBTHERAPEUTIC_ANTIXA
            and len(values) >= 2
            and values[-1] < values[0]
        )

        if (significant_rise or (rising and elevated)) and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            _add(
                "rising_antixa_on_heparin",
                sev,
                (
                    "RESEARCH USE ONLY: Rising anti-Xa trend on heparin-class "
                    f"therapy (values {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + f"). Agents: {', '.join(agents)}. Anti-Xa monitoring "
                    "bridge distinct from HeparinPlateletTrendBridge HIT-risk "
                    "platelet trends. Never modifies medications. Confirm with "
                    "a qualified clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / "
                    "Gemini 3.x / Kimi K2."
                ),
            )

        if elevated and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            kind = (
                "supratherapeutic_antixa_on_heparin" if critical else "elevated_antixa_on_heparin"
            )
            _add(
                kind,
                sev,
                (
                    "RESEARCH USE ONLY: "
                    + ("Supratherapeutic" if critical else "Elevated")
                    + f" anti-Xa on heparin-class therapy (latest {latest}, "
                    f"series {values}). Agents: {', '.join(agents)}. Anti-Xa "
                    "bridge distinct from HeparinPlateletTrendBridge. Never "
                    "modifies medications. Confirm with a qualified clinician; "
                    "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if subtherapeutic and agents:
            _add(
                "subtherapeutic_antixa_on_heparin",
                Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Falling/subtherapeutic anti-Xa on "
                    f"heparin-class therapy (latest {latest}, series {values}). "
                    f"Agents: {', '.join(agents)}. Anti-Xa bridge distinct from "
                    "HeparinPlateletTrendBridge. Never modifies medications. "
                    "Confirm with a qualified clinician; prefer GPT-5.5 / "
                    "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if (significant_rise or elevated or subtherapeutic) and agents:
            _add(
                "heparin_antixa_monitoring_advisory",
                Severity.CRITICAL if critical else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Heparin/LMWH anti-Xa monitoring "
                    f"advisory for agents {', '.join(agents)} (anti-Xa {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + "). Distinct from HeparinPlateletTrendBridge HIT-risk "
                    "platelet cues. Never modifies medications. Confirm with a "
                    "qualified clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / "
                    "Gemini 3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("heparin_antixa_trend_bridge_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
