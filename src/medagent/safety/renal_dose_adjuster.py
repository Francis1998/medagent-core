"""Renal dose adjuster — banded regimen suggestions by eGFR.

The existing :class:`~medagent.safety.renal_dose_checker.RenalDoseChecker`
emits avoid / reduce-dose advisories when eGFR falls at or below a threshold.
It does **not** propose concrete educational regimen bands.

This adjuster fills that gap for a small curated panel (gabapentin, metformin,
pregabalin, allopurinol, enoxaparin, digoxin, and similar). Given a known eGFR
it selects the matching renal band and emits an advisory
:class:`~medagent.models.RenalDoseAdjustment` with ``band_label`` and
``suggested_regimen``. Findings are RESEARCH USE ONLY and never modify
medications or prescribe therapy.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, RenalDoseAdjustment, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Each agent maps to ordered bands: (max_egfr_inclusive, band_label, regimen, severity).
# Bands are evaluated from lowest max_egfr upward; first match wins.
# A sentinel band with max_egfr=inf covers preserved renal function (usually no finding).
_PANEL: Final[dict[str, tuple[tuple[float, str, str, Severity], ...]]] = {
    "gabapentin": (
        (
            15.0,
            "egfr_lt_15",
            "educational cue: consider 100–300 mg once daily after dialysis timing review",
            Severity.HIGH,
        ),
        (
            29.0,
            "egfr_15_29",
            "educational cue: consider 100–300 mg once daily (renally adjusted)",
            Severity.HIGH,
        ),
        (
            59.0,
            "egfr_30_59",
            "educational cue: consider 200–700 mg/day in divided doses",
            Severity.MODERATE,
        ),
        (
            89.0,
            "egfr_60_89",
            "educational cue: consider 400–1400 mg/day in divided doses",
            Severity.LOW,
        ),
    ),
    "pregabalin": (
        (
            30.0,
            "egfr_le_30",
            "educational cue: consider 25–75 mg once daily (renally adjusted)",
            Severity.HIGH,
        ),
        (
            60.0,
            "egfr_31_60",
            "educational cue: consider 75–300 mg/day in 2–3 divided doses",
            Severity.MODERATE,
        ),
    ),
    "metformin": (
        (
            30.0,
            "egfr_lt_30",
            "educational cue: generally avoid metformin below eGFR 30",
            Severity.HIGH,
        ),
        (
            45.0,
            "egfr_30_45",
            "educational cue: consider dose reduction / cautious continuation review",
            Severity.MODERATE,
        ),
    ),
    "allopurinol": (
        (
            30.0,
            "egfr_le_30",
            "educational cue: consider starting ≤50–100 mg daily with oxypurinol caution",
            Severity.MODERATE,
        ),
        (
            60.0,
            "egfr_31_60",
            "educational cue: consider starting ≤100–200 mg daily",
            Severity.LOW,
        ),
    ),
    "enoxaparin": (
        (
            30.0,
            "egfr_lt_30",
            "educational cue: consider therapeutic 1 mg/kg once daily (renally adjusted cue)",
            Severity.HIGH,
        ),
    ),
    "digoxin": (
        (
            50.0,
            "egfr_le_50",
            "educational cue: consider reduced maintenance dose / extend interval",
            Severity.MODERATE,
        ),
    ),
    "atenolol": (
        (
            35.0,
            "egfr_le_35",
            "educational cue: consider dose reduction or extended dosing interval",
            Severity.MODERATE,
        ),
    ),
    "colchicine": (
        (
            30.0,
            "egfr_le_30",
            "educational cue: consider reduced dose / avoid loading regimens",
            Severity.HIGH,
        ),
    ),
}


class RenalDoseAdjuster:
    """Emit banded renal regimen suggestions for a curated medication panel."""

    def check(
        self,
        medications: list[Medication],
        egfr: float | None,
    ) -> list[RenalDoseAdjustment]:
        """Return advisory banded regimen suggestions for matching agents.

        Args:
            medications: Active patient medications.
            egfr: Estimated glomerular filtration rate in mL/min/1.73m^2, or
                None when unknown.

        Returns:
            One :class:`RenalDoseAdjustment` per matching medication that falls
            into a curated renal band, ordered by descending severity then
            medication name. Empty when eGFR is unknown or no band applies.
            Distinct from :class:`RenalDoseChecker`, which only emits
            avoid / reduce-dose flags without regimen bands.
        """
        if egfr is None:
            logger.info("renal_dose_adjuster_checked", findings=0, eligible=False)
            return []

        findings: list[RenalDoseAdjustment] = []
        for medication in medications:
            tokens = self._tokens(medication.name)
            agents = sorted(tokens & set(_PANEL))
            if not agents:
                continue
            # Prefer the highest-severity band among matched agents.
            best: RenalDoseAdjustment | None = None
            for agent in agents:
                band = self._select_band(agent, egfr)
                if band is None:
                    continue
                band_label, suggested_regimen, severity = band
                candidate = RenalDoseAdjustment(
                    medication=medication.name,
                    agent=agent,
                    egfr=egfr,
                    band_label=band_label,
                    suggested_regimen=suggested_regimen,
                    severity=severity,
                    rationale=(
                        "RESEARCH USE ONLY: Medication "
                        f"'{medication.name}' matched renal adjuster agent "
                        f"'{agent}' at eGFR {egfr:g} mL/min/1.73m^2 "
                        f"(band '{band_label}'). Educational suggested regimen: "
                        f"{suggested_regimen}. This emits banded regimen cues "
                        "and is distinct from RenalDoseChecker avoid/reduce "
                        "flags. Not a prescription. Confirm with a qualified "
                        "clinician; prefer frontier summarization with GPT-5.5 / "
                        "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                    ),
                )
                if best is None or (
                    _SEVERITY_RANK[candidate.severity],
                    candidate.agent,
                ) > (
                    _SEVERITY_RANK[best.severity],
                    best.agent,
                ):
                    best = candidate
            if best is not None:
                findings.append(best)

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.medication))
        logger.info("renal_dose_adjuster_checked", findings=len(findings), eligible=True)
        return findings

    @staticmethod
    def _select_band(agent: str, egfr: float) -> tuple[str, str, Severity] | None:
        """Return (band_label, suggested_regimen, severity) for the first matching band."""
        for max_egfr, band_label, regimen, severity in _PANEL[agent]:
            if egfr <= max_egfr:
                return band_label, regimen, severity
        return None

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
