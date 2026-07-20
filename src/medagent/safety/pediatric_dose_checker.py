"""Pediatric dose / age-contraindication safety checker.

Pediatric patients are not simply small adults: several medications are
age-contraindicated in children (for example codeine and tramadol under 12
years for ultra-rapid CYP2D6 / respiratory-depression risk, and tetracyclines
under 8 years for tooth discoloration and bone effects), and many others carry
weight-based (mg/kg) daily maximums that adult tablet strengths can exceed.
This hazard is neither a drug–drug interaction, an allergy, a duplicate-therapy
flag, a pregnancy risk, a QT/serotonin/anticholinergic burden, an older-adult
Beers judgement, nor a renal/hepatic dose judgement: it is an *age- and
weight-conditioned* paediatric appropriateness judgement, so it is not surfaced
by the existing checkers.

This checker matches active medications to a conservative paediatric panel
(whole-token matching, never loose substrings), flags age contraindications,
and optionally compares a parsed daily mg dose against a per-agent mg/kg/day
maximum when weight is known. It is deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, PediatricDoseRisk, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# First signed decimal in free text (dose strength).
_NUMBER_PATTERN: Final[re.Pattern[str]] = re.compile(r"[-+]?\d*\.\d+|[-+]?\d+")
_MG_PATTERN: Final[re.Pattern[str]] = re.compile(r"(\d+(?:\.\d+)?)\s*mg\b", re.IGNORECASE)

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


class _PediatricRule:
    """A canonical paediatric dose / age-contraindication panel entry.

    Attributes:
        agent: Canonical medication token.
        min_age_years: Exclusive minimum age; patients strictly younger are
            age-contraindicated. None when age is not gated.
        max_mg_per_kg_day: Maximum total daily dose in mg/kg/day. None when no
            weight-based ceiling is modeled.
        severity: Severity assigned when the rule fires.
        rationale: Short clinical reason for the rule.
    """

    __slots__ = ("agent", "max_mg_per_kg_day", "min_age_years", "rationale", "severity")

    def __init__(
        self,
        agent: str,
        min_age_years: float | None,
        max_mg_per_kg_day: float | None,
        severity: Severity,
        rationale: str,
    ) -> None:
        """Initialize a panel entry."""
        self.agent = agent
        self.min_age_years = min_age_years
        self.max_mg_per_kg_day = max_mg_per_kg_day
        self.severity = severity
        self.rationale = rationale


# Conservative, widely-cited paediatric panel. Age gates and mg/kg ceilings are
# RESEARCH USE ONLY approximations of common labelling cautions.
_PANEL: Final[tuple[_PediatricRule, ...]] = (
    _PediatricRule(
        "codeine",
        12.0,
        None,
        Severity.CRITICAL,
        "codeine is contraindicated under 12 years (CYP2D6 ultra-rapid metabolizer / "
        "respiratory-depression risk)",
    ),
    _PediatricRule(
        "tramadol",
        12.0,
        None,
        Severity.CRITICAL,
        "tramadol is contraindicated under 12 years (respiratory-depression risk)",
    ),
    _PediatricRule(
        "tetracycline",
        8.0,
        None,
        Severity.HIGH,
        "tetracyclines are generally avoided under 8 years (permanent tooth discoloration "
        "and bone effects)",
    ),
    _PediatricRule(
        "doxycycline",
        8.0,
        None,
        Severity.HIGH,
        "tetracyclines are generally avoided under 8 years (permanent tooth discoloration "
        "and bone effects)",
    ),
    _PediatricRule(
        "minocycline",
        8.0,
        None,
        Severity.HIGH,
        "tetracyclines are generally avoided under 8 years (permanent tooth discoloration "
        "and bone effects)",
    ),
    _PediatricRule(
        "aspirin",
        16.0,
        None,
        Severity.HIGH,
        "aspirin is generally avoided in children/adolescents with viral illness "
        "(Reye syndrome risk); panel uses age <16 as a conservative gate",
    ),
    _PediatricRule(
        "acetaminophen",
        None,
        75.0,
        Severity.HIGH,
        "acetaminophen total daily dose should not exceed ~75 mg/kg/day in children "
        "(hepatotoxicity risk)",
    ),
    _PediatricRule(
        "paracetamol",
        None,
        75.0,
        Severity.HIGH,
        "paracetamol (acetaminophen) total daily dose should not exceed ~75 mg/kg/day "
        "in children (hepatotoxicity risk)",
    ),
    _PediatricRule(
        "ibuprofen",
        None,
        40.0,
        Severity.MODERATE,
        "ibuprofen total daily dose should not exceed ~40 mg/kg/day in children",
    ),
    _PediatricRule(
        "amoxicillin",
        None,
        90.0,
        Severity.MODERATE,
        "amoxicillin high-dose regimens are typically capped near ~90 mg/kg/day",
    ),
)


class PediatricDoseChecker:
    """Flag paediatric age contraindications and mg/kg daily-dose excesses."""

    def check(
        self,
        medications: list[Medication],
        age_years: float | None,
        weight_kg: float | None = None,
    ) -> list[PediatricDoseRisk]:
        """Return paediatric dose / age findings for active medications.

        Args:
            medications: Active patient medications.
            age_years: Patient age in years, or None when unknown.
            weight_kg: Patient weight in kilograms, or None when unknown.
                Required to evaluate mg/kg daily-dose ceilings.

        Returns:
            One :class:`PediatricDoseRisk` per matching rule violation, ordered
            by descending severity then medication name. An empty list is
            returned when age and weight are both unknown, or when no panel
            rule is violated.
        """
        findings: list[PediatricDoseRisk] = []
        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue
            for rule in _PANEL:
                if rule.agent not in tokens:
                    continue
                age_contraindicated = (
                    rule.min_age_years is not None
                    and age_years is not None
                    and age_years < rule.min_age_years
                )
                dose_mg_per_kg_day: float | None = None
                max_mg_per_kg_day = rule.max_mg_per_kg_day
                exceeds_mg_kg = False
                if rule.max_mg_per_kg_day is not None and weight_kg is not None and weight_kg > 0:
                    daily_mg = self._parse_daily_mg(medication)
                    if daily_mg is not None:
                        dose_mg_per_kg_day = daily_mg / weight_kg
                        exceeds_mg_kg = dose_mg_per_kg_day > rule.max_mg_per_kg_day

                if not age_contraindicated and not exceeds_mg_kg:
                    continue

                finding_kind = (
                    "age_contraindication"
                    if age_contraindicated and not exceeds_mg_kg
                    else "mg_per_kg_excess"
                    if exceeds_mg_kg and not age_contraindicated
                    else "age_and_mg_per_kg"
                )
                parts = [
                    f"Medication '{medication.name}' ({rule.agent}) triggered a paediatric "
                    f"safety rule ({finding_kind}): {rule.rationale}."
                ]
                if age_contraindicated and rule.min_age_years is not None:
                    parts.append(
                        f" Patient age {age_years:g} years is below the "
                        f"{rule.min_age_years:g}-year threshold."
                    )
                if (
                    exceeds_mg_kg
                    and dose_mg_per_kg_day is not None
                    and max_mg_per_kg_day is not None
                ):
                    parts.append(
                        f" Calculated dose {dose_mg_per_kg_day:.1f} mg/kg/day exceeds the "
                        f"{max_mg_per_kg_day:g} mg/kg/day maximum"
                        f" (weight {weight_kg:g} kg)."
                    )
                findings.append(
                    PediatricDoseRisk(
                        medication=medication.name,
                        agent=rule.agent,
                        age_years=age_years,
                        weight_kg=weight_kg,
                        min_age_years=rule.min_age_years,
                        dose_mg_per_kg_day=dose_mg_per_kg_day,
                        max_mg_per_kg_day=max_mg_per_kg_day,
                        finding_kind=finding_kind,
                        severity=rule.severity,
                        rationale="".join(parts),
                    )
                )
        findings.sort(
            key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.medication.lower())
        )
        logger.info("pediatric_dose_checked", findings=len(findings))
        return findings

    @classmethod
    def _parse_daily_mg(cls, medication: Medication) -> float | None:
        """Parse a total daily dose in mg from medication name / dosage / frequency.

        Args:
            medication: Medication whose free-text fields may carry strength and
                frequency.

        Returns:
            Total daily mg, or None when strength cannot be parsed.
        """
        blob = " ".join(
            part for part in (medication.name, medication.dosage, medication.frequency) if part
        )
        mg_match = _MG_PATTERN.search(blob)
        if not mg_match:
            return None
        strength = float(mg_match.group(1))
        multiplier = 1.0
        for pattern, factor in _FREQUENCY_MULTIPLIERS:
            if pattern.search(blob):
                multiplier = factor
                break
        return strength * multiplier

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a name.

        Args:
            name: Medication name text (may contain separators).

        Returns:
            Set of component tokens.
        """
        return set(re.findall(r"[a-z0-9]+", name.lower()))
