"""Lab trend alert bridge - serial labs to advisory trend safety cues.

The existing :class:`~medagent.safety.lab_critical_value_checker.LabCriticalValueChecker`
flags **single-draw** panic thresholds. It does not inspect ordered serial values
for directional trends such as rising creatinine, falling platelets, or rising INR.

This bridge fills that gap: it accepts serial lab dicts
``{name, value, unit, drawn_at}``, groups by analyte, sorts by draw time, and
emits advisory :class:`~medagent.models.LabTrendAlert` findings. Findings are
RESEARCH USE ONLY and never modify medications.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any, Final

from medagent.logging_config import get_logger
from medagent.models import LabTrendAlert, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical analyte -> aliases (lowercase)
_ALIASES: Final[dict[str, frozenset[str]]] = {
    "creatinine": frozenset({"creatinine", "creat", "serum creatinine", "scr"}),
    "platelets": frozenset({"platelets", "platelet", "plt", "platelet count"}),
    "inr": frozenset({"inr", "international normalized ratio"}),
    "potassium": frozenset({"potassium", "k", "k+", "serum potassium"}),
    "hemoglobin": frozenset({"hemoglobin", "haemoglobin", "hgb", "hb"}),
    "alt": frozenset({"alt", "alanine aminotransferase", "sgpt"}),
}


class LabTrendAlertBridge:
    """Map serial lab draws to advisory trend safety cues."""

    def check(self, labs: Sequence[Mapping[str, Any]]) -> list[LabTrendAlert]:
        """Return trend alerts for serial laboratory values.

        Args:
            labs: Ordered or unordered draws, each a mapping with keys
                ``name``, ``value``, ``unit`` (optional), and ``drawn_at``
                (sortable string/timestamp).

        Returns:
            Zero or more :class:`LabTrendAlert` findings. Distinct from
            single-draw :class:`LabCriticalValueChecker` panic flags. Never
            modifies medications.
        """
        series: dict[str, list[tuple[str, float, str]]] = defaultdict(list)
        for entry in labs:
            name = str(entry.get("name", "")).strip()
            if not name:
                continue
            canonical = self._canonical(name)
            if canonical is None:
                continue
            raw_value = entry.get("value")
            try:
                value = float(raw_value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            unit = str(entry.get("unit") or "")
            drawn_at = str(entry.get("drawn_at") or "")
            series[canonical].append((drawn_at, value, unit))

        findings: list[LabTrendAlert] = []
        for analyte, points in series.items():
            if len(points) < 2:
                continue
            points_sorted = sorted(points, key=lambda item: item[0])
            values = [value for _drawn, value, _unit in points_sorted]
            drawn_ats = [drawn for drawn, _value, _unit in points_sorted]
            unit = next((u for _d, _v, u in reversed(points_sorted) if u), "")
            first, last = values[0], values[-1]
            delta = last - first
            percent = (delta / first * 100.0) if first != 0 else None
            alert = self._evaluate(analyte, values, drawn_ats, unit, delta, percent)
            if alert is not None:
                findings.append(alert)

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("lab_trend_alert_bridge_checked", findings=len(findings))
        return findings

    def _evaluate(
        self,
        analyte: str,
        values: list[float],
        drawn_ats: list[str],
        unit: str,
        delta: float,
        percent: float | None,
    ) -> LabTrendAlert | None:
        """Return a trend alert when curated rules fire for ``analyte``."""
        first, last = values[0], values[-1]

        if analyte == "creatinine" and (
            delta >= 0.3 or (percent is not None and percent >= 20.0 and delta > 0)
        ):
            severity = Severity.CRITICAL if delta >= 0.5 or (percent or 0) >= 50 else Severity.HIGH
            return LabTrendAlert(
                finding_kind="rising_creatinine",
                lab_name=analyte,
                values=values,
                unit=unit,
                drawn_ats=drawn_ats,
                delta=delta,
                percent_change=percent,
                severity=severity,
                rationale=(
                    "RESEARCH USE ONLY: Lab trend bridge detected rising creatinine "
                    f"from {first:g} to {last:g} {unit} (delta {delta:+.3g}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + "). Advisory serial-lab cue distinct from single-draw "
                    "LabCriticalValueChecker. Never modifies medications. Confirm "
                    "with a qualified clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / "
                    "Gemini 3.x / Kimi K2."
                ),
            )

        if analyte == "platelets" and (
            (percent is not None and percent <= -20.0)
            or (first > 0 and last < 100 and last < first)
        ):
            severity = Severity.CRITICAL if last < 50 or (percent or 0) <= -40 else Severity.HIGH
            return LabTrendAlert(
                finding_kind="falling_platelets",
                lab_name=analyte,
                values=values,
                unit=unit,
                drawn_ats=drawn_ats,
                delta=delta,
                percent_change=percent,
                severity=severity,
                rationale=(
                    "RESEARCH USE ONLY: Lab trend bridge detected falling platelets "
                    f"from {first:g} to {last:g} {unit} (delta {delta:+.3g}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + "). Advisory serial-lab cue distinct from single-draw "
                    "LabCriticalValueChecker. Never modifies medications. Confirm "
                    "with a qualified clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / "
                    "Gemini 3.x / Kimi K2."
                ),
            )

        if analyte == "inr" and (delta >= 0.5 or (last >= 3.5 and last > first)):
            severity = Severity.CRITICAL if last >= 4.5 or delta >= 1.5 else Severity.HIGH
            return LabTrendAlert(
                finding_kind="rising_inr",
                lab_name=analyte,
                values=values,
                unit=unit,
                drawn_ats=drawn_ats,
                delta=delta,
                percent_change=percent,
                severity=severity,
                rationale=(
                    "RESEARCH USE ONLY: Lab trend bridge detected rising INR "
                    f"from {first:g} to {last:g} (delta {delta:+.3g}). Advisory "
                    "serial-lab cue distinct from single-draw LabCriticalValueChecker. "
                    "Never modifies medications. Confirm with a qualified clinician; "
                    "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if analyte == "potassium" and delta >= 0.5 and last >= 5.0:
            severity = Severity.CRITICAL if last >= 6.0 else Severity.HIGH
            return LabTrendAlert(
                finding_kind="rising_potassium",
                lab_name=analyte,
                values=values,
                unit=unit,
                drawn_ats=drawn_ats,
                delta=delta,
                percent_change=percent,
                severity=severity,
                rationale=(
                    "RESEARCH USE ONLY: Lab trend bridge detected rising potassium "
                    f"from {first:g} to {last:g} {unit} (delta {delta:+.3g}). "
                    "Advisory serial-lab cue distinct from single-draw "
                    "LabCriticalValueChecker. Never modifies medications. Confirm "
                    "with a qualified clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / "
                    "Gemini 3.x / Kimi K2."
                ),
            )

        if analyte == "hemoglobin" and (
            delta <= -1.0 or (percent is not None and percent <= -10.0 and delta < 0)
        ):
            severity = Severity.HIGH if last < 8.0 or delta <= -2.0 else Severity.MODERATE
            return LabTrendAlert(
                finding_kind="falling_hemoglobin",
                lab_name=analyte,
                values=values,
                unit=unit,
                drawn_ats=drawn_ats,
                delta=delta,
                percent_change=percent,
                severity=severity,
                rationale=(
                    "RESEARCH USE ONLY: Lab trend bridge detected falling hemoglobin "
                    f"from {first:g} to {last:g} {unit} (delta {delta:+.3g}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + "). Advisory serial-lab cue distinct from single-draw "
                    "LabCriticalValueChecker. Never modifies medications. Confirm "
                    "with a qualified clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / "
                    "Gemini 3.x / Kimi K2."
                ),
            )

        if analyte == "alt" and (
            delta >= 20 or (percent is not None and percent >= 50.0 and delta > 0)
        ):
            severity = Severity.HIGH if last >= 200 or (percent or 0) >= 100 else Severity.MODERATE
            return LabTrendAlert(
                finding_kind="rising_alt",
                lab_name=analyte,
                values=values,
                unit=unit,
                drawn_ats=drawn_ats,
                delta=delta,
                percent_change=percent,
                severity=severity,
                rationale=(
                    "RESEARCH USE ONLY: Lab trend bridge detected rising ALT "
                    f"from {first:g} to {last:g} {unit} (delta {delta:+.3g}"
                    + (f", {percent:.1f}%" if percent is not None else "")
                    + "). Advisory serial-lab cue distinct from single-draw "
                    "LabCriticalValueChecker. Never modifies medications. Confirm "
                    "with a qualified clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / "
                    "Gemini 3.x / Kimi K2."
                ),
            )

        return None

    @staticmethod
    def _canonical(name: str) -> str | None:
        """Map a reported lab name to a curated canonical analyte."""
        key = " ".join(name.lower().split())
        for canonical, aliases in _ALIASES.items():
            if key in aliases:
                return canonical
        # whole-token fallback for compounds like "serum creatinine"
        tokens = set(key.replace("-", " ").split())
        for canonical, aliases in _ALIASES.items():
            if canonical in tokens or any(alias in tokens for alias in aliases if " " not in alias):
                if canonical == "potassium" and tokens == {"k"}:
                    return "potassium"
                if any(alias == key for alias in aliases):
                    return canonical
                if canonical in tokens:
                    return canonical
        return None
