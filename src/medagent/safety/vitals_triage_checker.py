"""Adult NEWS2-style single-parameter vitals triage checker.

Maps SpO2, respiratory rate, systolic blood pressure, heart rate, and
temperature onto educational NEWS2 single-parameter score bands and emits
advisory severity findings. This is RESEARCH USE ONLY triage education —
not a clinical early-warning system, not a substitute for local NEWS2 /
MEWS protocols, and distinct from MedPrompt-style clinical triage prompting.

Findings never modify vitals, order oxygen, or escalate care automatically.
"""

from __future__ import annotations

from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Severity, VitalSign, VitalsTriageRisk

logger = get_logger(__name__)

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical parameter aliases -> (canonical_name, default_unit).
_PARAMETER_ALIASES: Final[dict[str, tuple[str, str]]] = {
    "spo2": ("spo2", "%"),
    "oxygen_saturation": ("spo2", "%"),
    "o2_sat": ("spo2", "%"),
    "o2sat": ("spo2", "%"),
    "respiratory_rate": ("respiratory_rate", "/min"),
    "rr": ("respiratory_rate", "/min"),
    "resp_rate": ("respiratory_rate", "/min"),
    "systolic_bp": ("systolic_bp", "mmHg"),
    "sbp": ("systolic_bp", "mmHg"),
    "systolic_blood_pressure": ("systolic_bp", "mmHg"),
    "heart_rate": ("heart_rate", "/min"),
    "hr": ("heart_rate", "/min"),
    "pulse": ("heart_rate", "/min"),
    "temperature": ("temperature", "C"),
    "temp": ("temperature", "C"),
    "body_temperature": ("temperature", "C"),
}

_PARAMETER_ORDER: Final[dict[str, int]] = {
    "spo2": 0,
    "respiratory_rate": 1,
    "systolic_bp": 2,
    "heart_rate": 3,
    "temperature": 4,
}


def _score_to_severity(score: int) -> Severity:
    """Map a NEWS2 single-parameter score (1–3) to advisory severity."""
    if score >= 3:
        return Severity.HIGH
    if score == 2:
        return Severity.MODERATE
    return Severity.LOW


def _news2_spo2(value: float) -> int:
    """NEWS2 Scale-1 SpO2 single-parameter score (educational approximation)."""
    if value <= 91:
        return 3
    if value <= 93:
        return 2
    if value <= 95:
        return 1
    return 0


def _news2_rr(value: float) -> int:
    """NEWS2 respiratory-rate single-parameter score."""
    if value <= 8:
        return 3
    if value <= 11:
        return 1
    if value <= 20:
        return 0
    if value <= 24:
        return 2
    return 3


def _news2_sbp(value: float) -> int:
    """NEWS2 systolic BP single-parameter score."""
    if value <= 90:
        return 3
    if value <= 100:
        return 2
    if value <= 110:
        return 1
    if value <= 219:
        return 0
    return 3


def _news2_hr(value: float) -> int:
    """NEWS2 heart-rate single-parameter score."""
    if value <= 40:
        return 3
    if value <= 50:
        return 1
    if value <= 90:
        return 0
    if value <= 110:
        return 1
    if value <= 130:
        return 2
    return 3


def _news2_temp(value: float) -> int:
    """NEWS2 temperature single-parameter score (°C)."""
    if value <= 35.0:
        return 3
    if value <= 36.0:
        return 1
    if value <= 38.0:
        return 0
    if value <= 39.0:
        return 1
    return 2


_SCORERS: Final[dict[str, object]] = {
    "spo2": _news2_spo2,
    "respiratory_rate": _news2_rr,
    "systolic_bp": _news2_sbp,
    "heart_rate": _news2_hr,
    "temperature": _news2_temp,
}


class VitalsTriageChecker:
    """Flag abnormal adult vitals using NEWS2-style single-parameter bands."""

    def check(self, vitals: list[VitalSign]) -> list[VitalsTriageRisk]:
        """Return advisory findings for vitals outside NEWS2 score-0 bands.

        Args:
            vitals: Adult vital-sign readings. Unrecognized parameter names are
                ignored. Temperature is interpreted in °C.

        Returns:
            One :class:`VitalsTriageRisk` per abnormal vital, ordered by
            descending severity then parameter name. Empty when all values are
            within score-0 bands or the list is empty.
        """
        findings: list[VitalsTriageRisk] = []
        for vital in vitals:
            canonical = self._canonicalize(vital.name)
            if canonical is None:
                continue
            parameter, default_unit = canonical
            scorer = _SCORERS[parameter]
            assert callable(scorer)
            score = int(scorer(vital.value))
            if score <= 0:
                continue
            unit = vital.unit or default_unit
            severity = _score_to_severity(score)
            findings.append(
                VitalsTriageRisk(
                    parameter=parameter,
                    value=vital.value,
                    unit=unit,
                    news2_score=score,
                    severity=severity,
                    rationale=(
                        "RESEARCH USE ONLY: Adult NEWS2-style single-parameter "
                        f"band for {parameter}={vital.value}{(' ' + unit) if unit else ''} "
                        f"maps to educational score {score} ({severity.value}). "
                        "This is advisory triage education, not a clinical "
                        "early-warning system. Confirm with local NEWS2/MEWS "
                        "protocols and a qualified clinician; prefer frontier "
                        "summarization with GPT-5.5 / Claude Sonnet 4.6 / "
                        "Gemini 3.x / Kimi K2."
                    ),
                )
            )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                _PARAMETER_ORDER.get(finding.parameter, 99),
                finding.parameter,
            )
        )
        logger.info("vitals_triage_checked", findings=len(findings), vitals=len(vitals))
        return findings

    @staticmethod
    def _canonicalize(name: str) -> tuple[str, str] | None:
        """Map a free-text vital name to (canonical_parameter, default_unit)."""
        key = name.strip().lower().replace(" ", "_").replace("-", "_")
        key = key.replace("%", "").replace("/", "_")
        # Collapse common punctuation variants.
        key = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in key)
        while "__" in key:
            key = key.replace("__", "_")
        key = key.strip("_")
        if key in _PARAMETER_ALIASES:
            return _PARAMETER_ALIASES[key]
        # Soft match: substring tokens for longer display names.
        for alias, canonical in _PARAMETER_ALIASES.items():
            if alias in key.split("_") or key == alias:
                return canonical
        # Phrase heuristics for FHIR display names.
        lowered = name.strip().lower()
        if "spo2" in lowered or "oxygen saturation" in lowered:
            return _PARAMETER_ALIASES["spo2"]
        if "respiratory rate" in lowered or "respiration rate" in lowered:
            return _PARAMETER_ALIASES["respiratory_rate"]
        if "systolic" in lowered and ("bp" in lowered or "blood pressure" in lowered):
            return _PARAMETER_ALIASES["systolic_bp"]
        if "heart rate" in lowered or lowered == "pulse":
            return _PARAMETER_ALIASES["heart_rate"]
        if "temperature" in lowered or lowered in {"temp", "body temp"}:
            return _PARAMETER_ALIASES["temperature"]
        return None
