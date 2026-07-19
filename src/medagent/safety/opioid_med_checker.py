"""Opioid morphine-equivalent dose (MED / MME) safety checker.

A patient's active opioid list can accumulate into a high total daily
morphine-equivalent dose (MED, also called morphine milligram equivalents /
MME) even when no single prescription looks extreme on its own — for example
oxycodone 10 mg QID plus hydrocodone 10 mg TID. High cumulative MED is
associated with overdose and respiratory-depression risk and is a CDC-cited
caution threshold (historically ≥90 MME/day). This hazard is neither a
drug–drug interaction, an allergy, a duplicate-therapy flag (intra-class
redundancy without dose), a pregnancy risk, a QT/serotonin/anticholinergic
burden, an age-conditioned Beers judgement, nor a renal/hepatic dose
judgement: it is a *dose-cumulative* judgement keyed on converted daily opioid
doses, so it is not surfaced by the existing checkers.

This checker matches active medications to a conservative oral-opioid panel
(whole-token matching, never loose substrings), parses a daily dose from the
medication name / dosage / frequency fields, converts each dose to MED using
CDC-style conversion factors, and elevates severity when the summed MED reaches
a configurable high-MED threshold (default 90.0). It is deterministic and
RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, OpioidMedRisk, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Default CDC-cited high daily MED / MME caution threshold.
_DEFAULT_HIGH_MED_THRESHOLD: Final[float] = 90.0

# Canonical oral opioid token -> (MME conversion factor, dose unit label).
# Factors follow commonly cited CDC oral MME conversion guidance (approximate,
# RESEARCH USE ONLY). Fentanyl is treated as a transdermal mcg/hr exposure
# (factor 2.4), not an oral mg dose.
_OPIOID_FACTORS: dict[str, tuple[float, str]] = {
    "morphine": (1.0, "mg/day"),
    "codeine": (0.15, "mg/day"),
    "hydrocodone": (1.0, "mg/day"),
    "oxycodone": (1.5, "mg/day"),
    "oxymorphone": (3.0, "mg/day"),
    "hydromorphone": (4.0, "mg/day"),
    "tramadol": (0.1, "mg/day"),
    "tapentadol": (0.4, "mg/day"),
    "meperidine": (0.1, "mg/day"),
    "methadone": (4.0, "mg/day"),  # simplified; true methadone factor is dose-dependent
    "fentanyl": (2.4, "mcg/hr"),
}

# First signed decimal in free text (dose strength).
_NUMBER_PATTERN: Final[re.Pattern[str]] = re.compile(r"[-+]?\d*\.\d+|[-+]?\d+")

# Strength patterns: "10 mg", "10mg", "25 mcg/hr", "25mcg/h".
_MG_PATTERN: Final[re.Pattern[str]] = re.compile(r"(\d+(?:\.\d+)?)\s*mg\b", re.IGNORECASE)
_MCG_HR_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:mcg|µg|ug)\s*/\s*h(?:r|our)?\b", re.IGNORECASE
)

# Frequency multipliers for daily-dose calculation.
_FREQUENCY_MULTIPLIERS: Final[tuple[tuple[re.Pattern[str], float], ...]] = (
    (re.compile(r"\bqid\b|\bfour times(?: a| per)? day\b", re.I), 4.0),
    (re.compile(r"\btid\b|\bthree times(?: a| per)? day\b", re.I), 3.0),
    (re.compile(r"\bbid\b|\btwice(?: a| per)? day\b|\btwo times(?: a| per)? day\b", re.I), 2.0),
    (re.compile(r"\bq4h\b|\bevery\s*4\s*hours?\b", re.I), 6.0),
    (re.compile(r"\bq6h\b|\bevery\s*6\s*hours?\b", re.I), 4.0),
    (re.compile(r"\bq8h\b|\bevery\s*8\s*hours?\b", re.I), 3.0),
    (re.compile(r"\bq12h\b|\bevery\s*12\s*hours?\b", re.I), 2.0),
    (re.compile(r"\bq24h\b|\bonce(?: a| per)? day\b|\bdaily\b|\bqday\b|\bqd\b", re.I), 1.0),
)


class OpioidMedChecker:
    """Flag cumulative opioid morphine-equivalent dose (MED / MME) risk."""

    def check(
        self,
        medications: list[Medication],
        high_med_threshold: float = _DEFAULT_HIGH_MED_THRESHOLD,
    ) -> list[OpioidMedRisk]:
        """Return one finding per opioid medication with a parseable daily dose.

        Each matched opioid contributes ``daily_dose × conversion_factor`` to the
        total MED. When the summed MED is at or above ``high_med_threshold``
        (default 90.0), every finding's severity is elevated to at least HIGH.

        Args:
            medications: Active patient medications.
            high_med_threshold: Daily MED threshold at or above which severity
                is elevated. Must be positive.

        Returns:
            One :class:`OpioidMedRisk` per opioid with a parseable dose, ordered
            by descending severity then medication name. Medications that do not
            match the opioid panel or lack a parseable dose are skipped. An empty
            list is returned when no opioid contributes.

        Raises:
            ValueError: If ``high_med_threshold`` is not positive.
        """
        if high_med_threshold <= 0:
            raise ValueError("high_med_threshold must be positive")

        matched: list[tuple[Medication, str, float, str, float, float]] = []
        for medication in medications:
            tokens = self._tokens(medication.name)
            candidates = sorted(tokens & set(_OPIOID_FACTORS))
            if not candidates:
                continue
            agent = candidates[0]
            factor, unit = _OPIOID_FACTORS[agent]
            daily_dose = self._parse_daily_dose(medication, agent)
            if daily_dose is None:
                continue
            contribution = daily_dose * factor
            matched.append((medication, agent, daily_dose, unit, factor, contribution))

        total_med = sum(item[5] for item in matched)
        high = total_med >= high_med_threshold

        findings: list[OpioidMedRisk] = []
        for medication, agent, daily_dose, unit, factor, contribution in matched:
            severity = Severity.HIGH if high else Severity.MODERATE
            if high:
                rationale = (
                    f"Medication '{medication.name}' contributes {contribution:g} MED "
                    f"({daily_dose:g} {unit} × factor {factor:g} for {agent}). Total daily "
                    f"MED across active opioids is {total_med:g}, which is at or above the "
                    f"high-MED threshold of {high_med_threshold:g}. High cumulative MED is "
                    "associated with overdose and respiratory-depression risk — review "
                    "whether the opioid regimen can be reduced or tapered."
                )
            else:
                rationale = (
                    f"Medication '{medication.name}' contributes {contribution:g} MED "
                    f"({daily_dose:g} {unit} × factor {factor:g} for {agent}). Total daily "
                    f"MED across active opioids is {total_med:g} (below the high-MED "
                    f"threshold of {high_med_threshold:g}). Monitor cumulative opioid dose."
                )
            findings.append(
                OpioidMedRisk(
                    medication=medication.name,
                    agent=agent,
                    daily_dose=daily_dose,
                    dose_unit=unit,
                    conversion_factor=factor,
                    med_contribution=contribution,
                    total_med=total_med,
                    high_med_threshold=high_med_threshold,
                    severity=severity,
                    rationale=rationale,
                )
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.medication))
        logger.info(
            "opioid_med_checked",
            findings=len(findings),
            total_med=total_med,
            high_med_threshold=high_med_threshold,
        )
        return findings

    @classmethod
    def _parse_daily_dose(cls, medication: Medication, agent: str) -> float | None:
        """Parse a daily dose for an opioid medication.

        Dose strength is taken from ``dosage``, then from ``name``. Frequency
        multipliers (BID, TID, QID, qNh, daily) are applied for oral agents.
        Fentanyl is treated as a continuous mcg/hr exposure (no frequency
        multiplier). When frequency is absent for an oral agent, once-daily is
        assumed.

        Args:
            medication: Medication entry.
            agent: Matched canonical opioid agent.

        Returns:
            Daily dose in the agent's native unit, or None when no strength is
            found.
        """
        blob = " ".join(
            part for part in (medication.dosage, medication.name, medication.frequency) if part
        )
        if not blob.strip():
            return None

        if agent == "fentanyl":
            mcg = cls._first_float(_MCG_HR_PATTERN, blob)
            if mcg is not None:
                return mcg
            # Fall back to a bare number only when the unit field/name implies mcg/hr.
            if re.search(r"mcg|µg|ug", blob, re.IGNORECASE):
                bare = _NUMBER_PATTERN.search(blob)
                if bare is not None:
                    try:
                        return float(bare.group())
                    except ValueError:
                        return None
            return None

        mg = cls._first_float(_MG_PATTERN, blob)
        if mg is None:
            bare = _NUMBER_PATTERN.search(blob)
            if bare is None:
                return None
            try:
                mg = float(bare.group())
            except ValueError:
                return None

        multiplier = cls._frequency_multiplier(blob)
        return mg * multiplier

    @staticmethod
    def _first_float(pattern: re.Pattern[str], text: str) -> float | None:
        """Return the first float captured by ``pattern``, or None."""
        match = pattern.search(text)
        if match is None:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _frequency_multiplier(text: str) -> float:
        """Return doses-per-day implied by free-text frequency cues.

        Args:
            text: Combined dosage / name / frequency text.

        Returns:
            Multiplier (default 1.0 when no frequency cue is present).
        """
        for pattern, multiplier in _FREQUENCY_MULTIPLIERS:
            if pattern.search(text):
                return multiplier
        return 1.0

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name.

        Args:
            name: Medication name (may contain brand/dose/component separators).

        Returns:
            Set of component tokens.
        """
        return set(re.findall(r"[a-z0-9]+", name.lower()))
