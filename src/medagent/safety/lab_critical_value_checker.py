"""Laboratory critical-value (panic-value) safety checker.

A laboratory result at or beyond a standardized *critical* (panic) threshold —
for example serum potassium >6.0 mmol/L, glucose <40 mg/dL, or an INR >5.0 —
signals a potentially life-threatening state that laboratories are required to
report to the ordering clinician without delay. This hazard is not a drug-drug
interaction, an allergy, a duplicate therapy, a pregnancy risk, a
QT/serotonin/anticholinergic burden, an age-conditioned Beers judgement, nor a
renal/hepatic dose judgement: it is a *result-value* judgement keyed on the lab
value itself, so it is not surfaced by the existing medication-keyed checkers.

This checker matches each reported :class:`~medagent.models.LabResult` to a
canonical analyte in a conservative panic-value panel (whole-token name matching,
never loose substrings), parses the numeric value, and flags it when the value is
at or below a low panic threshold or at or above a high panic threshold. It is
deterministic and RESEARCH USE ONLY, complementing the renal-dose (eGFR) and
hepatic-dose (Child-Pugh) checkers.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import LabCriticalValueRisk, LabResult, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Matches the first signed decimal number in a free-text value (e.g. "6.8" in
# "6.8 mmol/L" or "-1.2"). Comparison/qualifier prefixes (">", "<") are ignored.
_NUMBER_PATTERN: Final[re.Pattern[str]] = re.compile(r"[-+]?\d*\.\d+|[-+]?\d+")


class _Analyte:
    """A canonical panic-value analyte definition.

    Attributes:
        canonical: Canonical analyte name.
        aliases: Whole-token aliases that identify the analyte in a test name.
        unit: Canonical unit for the thresholds.
        low: Low panic threshold (value at or below is critical), or None.
        high: High panic threshold (value at or above is critical), or None.
        severity: Severity assigned to a crossing of either threshold.
    """

    __slots__ = ("aliases", "canonical", "high", "low", "severity", "unit")

    def __init__(
        self,
        canonical: str,
        aliases: set[str],
        unit: str,
        low: float | None,
        high: float | None,
        severity: Severity,
    ) -> None:
        """Initialize an analyte definition."""
        self.canonical = canonical
        self.aliases = aliases
        self.unit = unit
        self.low = low
        self.high = high
        self.severity = severity


# Conservative, widely-cited adult critical-value panel. Thresholds are the
# outer panic bounds (well beyond the ordinary reference range), not routine
# abnormal flags. Aliases are matched as whole tokens of the reported test name.
_ANALYTES: Final[tuple[_Analyte, ...]] = (
    _Analyte("potassium", {"potassium", "k+"}, "mmol/L", 2.5, 6.0, Severity.CRITICAL),
    _Analyte("sodium", {"sodium", "na+"}, "mmol/L", 120.0, 160.0, Severity.CRITICAL),
    _Analyte("glucose", {"glucose"}, "mg/dL", 40.0, 500.0, Severity.CRITICAL),
    _Analyte("calcium", {"calcium"}, "mg/dL", 6.0, 13.0, Severity.CRITICAL),
    _Analyte("magnesium", {"magnesium"}, "mg/dL", 1.0, 4.7, Severity.HIGH),
    _Analyte("inr", {"inr"}, "ratio", None, 5.0, Severity.CRITICAL),
    _Analyte(
        "hemoglobin", {"hemoglobin", "haemoglobin", "hgb", "hb"}, "g/dL", 7.0, 20.0, Severity.HIGH
    ),
    _Analyte(
        "platelets", {"platelets", "platelet", "plt"}, "x10^3/uL", 20.0, 1000.0, Severity.CRITICAL
    ),
    _Analyte("wbc", {"wbc", "leukocytes", "leucocytes"}, "x10^3/uL", 2.0, 30.0, Severity.HIGH),
    _Analyte("creatinine", {"creatinine"}, "mg/dL", None, 7.4, Severity.HIGH),
    _Analyte("ph", {"ph"}, "units", 7.2, 7.6, Severity.CRITICAL),
    _Analyte("bicarbonate", {"bicarbonate", "hco3"}, "mmol/L", 10.0, 40.0, Severity.HIGH),
)


class LabCriticalValueChecker:
    """Flag laboratory results whose value crosses a critical (panic) threshold."""

    def check(self, lab_results: list[LabResult]) -> list[LabCriticalValueRisk]:
        """Return critical-value findings for a patient's lab results.

        A finding is produced when a result matches a panel analyte, its value
        parses to a number, and that value is at or below the analyte's low panic
        threshold or at or above its high panic threshold.

        Args:
            lab_results: Reported laboratory results.

        Returns:
            One :class:`LabCriticalValueRisk` per result crossing a critical
            threshold, ordered by descending severity then canonical test name.
            An empty list is returned when no result crosses a threshold.
        """
        findings: list[LabCriticalValueRisk] = []
        for result in lab_results:
            analyte = self._match_analyte(result.test_name)
            if analyte is None:
                continue
            value = self._parse_value(result.value)
            if value is None:
                continue

            if analyte.low is not None and value <= analyte.low:
                direction, threshold = "critically low", analyte.low
            elif analyte.high is not None and value >= analyte.high:
                direction, threshold = "critically high", analyte.high
            else:
                continue

            unit = result.unit or analyte.unit
            rationale = (
                f"Lab '{result.test_name}' ({analyte.canonical}) is {value:g} {unit}, which is "
                f"{direction} (critical threshold {threshold:g} {analyte.unit}). This is a panic "
                "value requiring urgent clinician notification and confirmation."
            )
            findings.append(
                LabCriticalValueRisk(
                    test_name=result.test_name,
                    canonical_test=analyte.canonical,
                    value=value,
                    unit=result.unit,
                    direction=direction,
                    threshold=threshold,
                    action="urgent clinician notification",
                    severity=analyte.severity,
                    rationale=rationale,
                )
            )

        findings.sort(
            key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.canonical_test)
        )
        logger.info("lab_critical_value_checked", findings=len(findings))
        return findings

    @staticmethod
    def _match_analyte(test_name: str) -> _Analyte | None:
        """Match a reported test name to a canonical panel analyte.

        Matching is on whole lowercase tokens of the test name, so a substring
        (for example ``potassium`` inside an unrelated word) does not trigger a
        match, and the first analyte whose aliases intersect the token set wins.

        Args:
            test_name: Reported laboratory test name.

        Returns:
            The matched analyte, or None when the test is not in the panel.
        """
        tokens = set(re.findall(r"[a-z0-9+]+", test_name.lower()))
        if not tokens:
            return None
        for analyte in _ANALYTES:
            if analyte.aliases & tokens:
                return analyte
        return None

    @staticmethod
    def _parse_value(value: str) -> float | None:
        """Parse the first numeric value from a free-text lab result string.

        Args:
            value: Reported result value (may carry units or a comparator).

        Returns:
            The parsed float, or None when no number is present.
        """
        match = _NUMBER_PATTERN.search(value)
        if match is None:
            return None
        try:
            return float(match.group())
        except ValueError:
            return None
