"""Pediatric weight-banded dose adjuster — educational regimen suggestions.

The existing :class:`~medagent.safety.pediatric_dose_checker.PediatricDoseChecker`
flags age contraindications and mg/kg daily-dose *excesses*. It does **not**
propose concrete educational weight-banded regimens.

This adjuster fills that gap for a small curated paediatric panel
(acetaminophen, ibuprofen, amoxicillin, cetirizine, ondansetron, and similar).
Given a known weight in kilograms it selects the matching weight band and emits
an advisory :class:`~medagent.models.PediatricWeightDoseAdjustment` with
``band_label`` and ``suggested_regimen``. Findings are RESEARCH USE ONLY and
never modify medications or prescribe therapy.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, PediatricWeightDoseAdjustment, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Each agent maps to ordered bands: (max_kg_inclusive, band_label, regimen, severity).
# Bands are evaluated from lowest max_kg upward; first match wins.
_PANEL: Final[dict[str, tuple[tuple[float, str, str, Severity], ...]]] = {
    "acetaminophen": (
        (
            10.0,
            "wt_lt_10kg",
            "educational cue: consider ~10–15 mg/kg/dose every 4–6 h (max ~75 mg/kg/day)",
            Severity.MODERATE,
        ),
        (
            20.0,
            "wt_10_20kg",
            "educational cue: consider ~10–15 mg/kg/dose every 4–6 h; typical 160–320 mg/dose range",
            Severity.LOW,
        ),
        (
            40.0,
            "wt_20_40kg",
            "educational cue: consider ~10–15 mg/kg/dose every 4–6 h; review adult-tablet strength",
            Severity.LOW,
        ),
    ),
    "paracetamol": (
        (
            10.0,
            "wt_lt_10kg",
            "educational cue: consider ~10–15 mg/kg/dose every 4–6 h (max ~75 mg/kg/day)",
            Severity.MODERATE,
        ),
        (
            20.0,
            "wt_10_20kg",
            "educational cue: consider ~10–15 mg/kg/dose every 4–6 h; typical 160–320 mg/dose range",
            Severity.LOW,
        ),
        (
            40.0,
            "wt_20_40kg",
            "educational cue: consider ~10–15 mg/kg/dose every 4–6 h; review adult-tablet strength",
            Severity.LOW,
        ),
    ),
    "ibuprofen": (
        (
            10.0,
            "wt_lt_10kg",
            "educational cue: consider ~5–10 mg/kg/dose every 6–8 h (max ~40 mg/kg/day)",
            Severity.MODERATE,
        ),
        (
            20.0,
            "wt_10_20kg",
            "educational cue: consider ~5–10 mg/kg/dose every 6–8 h; typical 100–200 mg/dose range",
            Severity.LOW,
        ),
        (
            40.0,
            "wt_20_40kg",
            "educational cue: consider ~5–10 mg/kg/dose every 6–8 h; review adult-tablet strength",
            Severity.LOW,
        ),
    ),
    "amoxicillin": (
        (
            10.0,
            "wt_lt_10kg",
            "educational cue: consider ~20–40 mg/kg/day divided (higher-dose pneumonia cues ~80–90)",
            Severity.MODERATE,
        ),
        (
            20.0,
            "wt_10_20kg",
            "educational cue: consider ~25–45 mg/kg/day divided BID–TID for common infections",
            Severity.LOW,
        ),
        (
            40.0,
            "wt_20_40kg",
            "educational cue: consider weight-based divided dosing; cap near adult usual doses",
            Severity.LOW,
        ),
    ),
    "cetirizine": (
        (
            10.0,
            "wt_lt_10kg",
            "educational cue: infant dosing generally deferred; clinician review required",
            Severity.HIGH,
        ),
        (
            20.0,
            "wt_10_20kg",
            "educational cue: consider ~2.5 mg once daily (age/weight dependent)",
            Severity.MODERATE,
        ),
        (
            40.0,
            "wt_20_40kg",
            "educational cue: consider ~5 mg once daily (age/weight dependent)",
            Severity.LOW,
        ),
    ),
    "ondansetron": (
        (
            15.0,
            "wt_lt_15kg",
            "educational cue: consider ~0.15 mg/kg/dose (single-dose cue); QT caution",
            Severity.MODERATE,
        ),
        (
            30.0,
            "wt_15_30kg",
            "educational cue: consider ~0.15 mg/kg/dose up to typical paediatric max cue",
            Severity.LOW,
        ),
    ),
    "diphenhydramine": (
        (
            10.0,
            "wt_lt_10kg",
            "educational cue: generally avoid routine use in young infants; clinician review",
            Severity.HIGH,
        ),
        (
            20.0,
            "wt_10_20kg",
            "educational cue: consider ~1 mg/kg/dose every 6 h (max cue ~5 mg/kg/day)",
            Severity.MODERATE,
        ),
    ),
}


class PediatricWeightDoseAdjuster:
    """Emit weight-banded paediatric regimen suggestions for a curated panel."""

    def check(
        self,
        medications: list[Medication],
        weight_kg: float | None,
    ) -> list[PediatricWeightDoseAdjustment]:
        """Return advisory weight-banded regimen suggestions for matching agents.

        Args:
            medications: Active patient medications.
            weight_kg: Patient weight in kilograms, or None when unknown.

        Returns:
            One :class:`PediatricWeightDoseAdjustment` per matching medication
            that falls into a curated weight band, ordered by descending
            severity then medication name. Empty when weight is unknown or no
            band applies. Distinct from :class:`PediatricDoseChecker`, which
            only flags age contraindications / mg/kg excesses without regimen
            bands.
        """
        if weight_kg is None or weight_kg <= 0:
            logger.info("pediatric_weight_dose_adjuster_checked", findings=0, eligible=False)
            return []

        findings: list[PediatricWeightDoseAdjustment] = []
        for medication in medications:
            tokens = self._tokens(medication.name)
            agents = sorted(tokens & set(_PANEL))
            if not agents:
                continue
            best: PediatricWeightDoseAdjustment | None = None
            for agent in agents:
                band = self._select_band(agent, weight_kg)
                if band is None:
                    continue
                band_label, suggested_regimen, severity = band
                candidate = PediatricWeightDoseAdjustment(
                    medication=medication.name,
                    agent=agent,
                    weight_kg=weight_kg,
                    band_label=band_label,
                    suggested_regimen=suggested_regimen,
                    severity=severity,
                    rationale=(
                        "RESEARCH USE ONLY: Medication "
                        f"'{medication.name}' matched paediatric weight-adjuster "
                        f"agent '{agent}' at weight {weight_kg:g} kg "
                        f"(band '{band_label}'). Educational suggested regimen: "
                        f"{suggested_regimen}. This emits weight-banded regimen "
                        "cues and is distinct from PediatricDoseChecker "
                        "age/excess flags. Not a prescription. Confirm with a "
                        "qualified clinician; prefer frontier summarization with "
                        "GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
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
        logger.info(
            "pediatric_weight_dose_adjuster_checked",
            findings=len(findings),
            eligible=True,
        )
        return findings

    @staticmethod
    def _select_band(agent: str, weight_kg: float) -> tuple[str, str, Severity] | None:
        """Return (band_label, suggested_regimen, severity) for the first matching band."""
        for max_kg, band_label, regimen, severity in _PANEL[agent]:
            if weight_kg <= max_kg:
                return band_label, regimen, severity
        return None

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
