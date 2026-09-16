"""Methotrexate + serial ALT/AST LFT hepatotoxicity-trend bridge.

The existing
:class:`~medagent.safety.mtx_folate_checker.MtxFolateChecker` covers
methotrexate without folate co-therapy,
:class:`~medagent.safety.mtx_tmpsmx_checker.MtxTmpsmxChecker` covers
methotrexate × TMP-SMX toxicity pairs, and
:class:`~medagent.safety.statin_lft_trend_bridge.StatinLftTrendBridge`
requires statin context for ALT/AST trends — none map methotrexate exposure
onto rising or elevated serial LFTs.

This bridge fills that gap: it combines methotrexate exposure with rising or
elevated serial ALT/AST values into advisory
:class:`~medagent.models.MtxLftTrendAlert` findings.
RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import Medication, MtxLftTrendAlert, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_MTX_AGENTS: Final[frozenset[str]] = frozenset(
    {
        "methotrexate",
        "trexall",
        "rheumatrex",
        "otrexup",
        "rasuvo",
        "xatmep",
    }
)

_ALT_ALIASES: Final[frozenset[str]] = frozenset(
    {"alt", "alanine aminotransferase", "sgpt", "alt/sgpt"}
)
_AST_ALIASES: Final[frozenset[str]] = frozenset(
    {"ast", "aspartate aminotransferase", "sgot", "ast/sgot"}
)

# Advisory LFT thresholds (U/L) — RESEARCH USE ONLY, not dosing guidance.
_ELEVATED_LFT: Final[float] = 80.0
_CRITICAL_LFT: Final[float] = 200.0
_MIN_RELATIVE_RISE: Final[float] = 0.5


class MtxLftTrendBridge:
    """Map methotrexate exposure + serial ALT/AST LFT trends to hepatotoxicity cues."""

    def check(
        self,
        medications: list[Medication],
        labs: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[MtxLftTrendAlert]:
        """Return methotrexate + LFT-trend hepatotoxicity advisories.

        Args:
            medications: Active medications.
            labs: Optional serial draws with ``name``, ``value``, optional
                ``unit`` / ``drawn_at`` (ALT and/or AST).

        Returns:
            Zero or more :class:`MtxLftTrendAlert` findings. Distinct from
            :class:`MtxFolateChecker`, :class:`MtxTmpsmxChecker`, and
            :class:`StatinLftTrendBridge`. Never modifies medications.
        """
        matched: list[tuple[str, str]] = []
        seen: set[str] = set()
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _MTX_AGENTS):
                if agent in seen:
                    continue
                matched.append((medication.name, agent))
                seen.add(agent)

        agents = [agent for _med, agent in matched]
        med_names = sorted({med for med, _agent in matched}, key=str.casefold)

        alt_series: list[tuple[str, float]] = []
        ast_series: list[tuple[str, float]] = []
        for entry in labs or []:
            name = str(entry.get("name", "")).strip().lower()
            try:
                value = float(entry.get("value"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            drawn = str(entry.get("drawn_at") or "")
            is_alt = (
                name in _ALT_ALIASES
                or "alanine" in name
                or ("alt" in name and "aspartate" not in name and "ast" not in name)
            )
            is_ast = (
                name in _AST_ALIASES
                or "aspartate" in name
                or (name == "ast" or name.startswith("ast "))
            )
            if is_alt:
                alt_series.append((drawn, value))
            elif is_ast:
                ast_series.append((drawn, value))

        alt_series.sort(key=lambda item: item[0])
        ast_series.sort(key=lambda item: item[0])
        alt_values = [value for _drawn, value in alt_series]
        ast_values = [value for _drawn, value in ast_series]
        if alt_values:
            values = alt_values
            drawn_ats = [drawn for drawn, _value in alt_series]
            analyte = "alt"
        else:
            values = ast_values
            drawn_ats = [drawn for drawn, _value in ast_series]
            analyte = "ast"

        latest = values[-1] if values else None
        percent: float | None = None
        if len(values) >= 2 and values[0] != 0:
            percent = (values[-1] - values[0]) / values[0] * 100.0

        if not agents:
            logger.info("mtx_lft_trend_bridge_checked", findings=0)
            return []

        findings: list[MtxLftTrendAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                MtxLftTrendAlert(
                    finding_kind=kind,
                    agents=agents,
                    medication_names=med_names,
                    alt_values=alt_values,
                    ast_values=ast_values,
                    drawn_ats=drawn_ats,
                    latest_lft=latest,
                    percent_change=percent,
                    severity=severity,
                    rationale=rationale,
                )
            )

        rising = len(values) >= 2 and values[-1] > values[0]
        significant_rise = percent is not None and percent >= _MIN_RELATIVE_RISE * 100.0
        elevated = latest is not None and latest >= _ELEVATED_LFT
        critical = latest is not None and latest >= _CRITICAL_LFT

        if (significant_rise or (rising and elevated)) and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            kind = "rising_alt_on_mtx" if analyte == "alt" else "rising_ast_on_mtx"
            _add(
                kind,
                sev,
                (
                    "RESEARCH USE ONLY: Rising "
                    f"{analyte.upper()} trend on methotrexate "
                    f"(values {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + f"). Agents: {', '.join(agents)}. Hepatotoxicity-risk "
                    "bridge distinct from MtxFolateChecker, MtxTmpsmxChecker, "
                    "and StatinLftTrendBridge. Never modifies medications. "
                    "Confirm with a qualified clinician; prefer GPT-5.5 / "
                    "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if elevated and agents:
            sev = Severity.CRITICAL if critical else Severity.HIGH
            _add(
                "elevated_lft_on_mtx",
                sev,
                (
                    "RESEARCH USE ONLY: Elevated LFT on methotrexate "
                    f"(latest {analyte.upper()} {latest}, series {values}). "
                    f"Agents: {', '.join(agents)}. Hepatotoxicity-risk bridge "
                    "distinct from MtxFolateChecker, MtxTmpsmxChecker, and "
                    "StatinLftTrendBridge. Never modifies medications. Confirm "
                    "with a qualified clinician; prefer GPT-5.5 / Claude Sonnet "
                    "4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if (significant_rise or elevated) and agents:
            _add(
                "mtx_hepatotoxicity_advisory",
                Severity.CRITICAL if critical else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Methotrexate hepatotoxicity advisory "
                    f"for agents {', '.join(agents)} ({analyte.upper()} {values}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + "). Distinct from MtxFolateChecker folate gaps, "
                    "MtxTmpsmxChecker TMP-SMX pairs, and StatinLftTrendBridge "
                    "statin context. Never modifies medications. Confirm with "
                    "a qualified clinician; prefer GPT-5.5 / Claude Sonnet "
                    "4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("mtx_lft_trend_bridge_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
