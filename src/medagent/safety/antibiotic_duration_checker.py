"""Antibiotic duration stewardship safety checker.

Antibiotic courses that exceed recommended duration or lack a documented stop
date increase resistance pressure, adverse effects, and C. difficile risk. The
existing antibiotic-stewardship checker flags fluoroquinolones without
indication, duplicate coverage, and prolonged-course cues parsed from
medication text; this checker complements it by evaluating explicit
`days_on_therapy` against recommended duration cadences and flagging missing
stop dates when therapy duration is known.

It flags antibiotic courses exceeding recommended duration or missing a stop
date when `days_on_therapy` is provided. Whole-token matching is used
throughout. Findings are deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import AntibioticDurationRisk, Medication, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_DEFAULT_MAX_DURATION_DAYS: Final[float] = 10.0

# Indication-type -> recommended maximum duration (days).
_INDICATION_DURATIONS: Final[dict[str, float]] = {
    "uti": 7.0,
    "pneumonia": 7.0,
    "skin": 7.0,
    "cellulitis": 7.0,
    "sinusitis": 10.0,
    "otitis": 10.0,
    "bacteremia": 14.0,
    "endocarditis": 42.0,
}

# Days on therapy at which a missing stop date is flagged.
_MISSING_STOP_DATE_MIN_DAYS: Final[int] = 3


@dataclass(frozen=True)
class _AntibioticRule:
    """A canonical antibiotic entry in the duration panel."""

    agent: str
    aliases: frozenset[str]
    default_max_days: float


_ANTIBIOTIC_PANEL: Final[tuple[_AntibioticRule, ...]] = (
    _AntibioticRule("amoxicillin", frozenset({"amoxicillin", "amoxil"}), 10.0),
    _AntibioticRule("amoxicillin_clavulanate", frozenset({"augmentin", "clavulanate"}), 10.0),
    _AntibioticRule("azithromycin", frozenset({"azithromycin", "azithro", "zithromax"}), 5.0),
    _AntibioticRule("cephalexin", frozenset({"cephalexin", "keflex"}), 10.0),
    _AntibioticRule("cefuroxime", frozenset({"cefuroxime"}), 10.0),
    _AntibioticRule("ceftriaxone", frozenset({"ceftriaxone", "rocephin"}), 14.0),
    _AntibioticRule("ciprofloxacin", frozenset({"ciprofloxacin", "cipro"}), 10.0),
    _AntibioticRule("clindamycin", frozenset({"clindamycin"}), 10.0),
    _AntibioticRule("doxycycline", frozenset({"doxycycline"}), 14.0),
    _AntibioticRule("levofloxacin", frozenset({"levofloxacin", "levaquin"}), 10.0),
    _AntibioticRule("metronidazole", frozenset({"metronidazole", "flagyl"}), 10.0),
    _AntibioticRule("nitrofurantoin", frozenset({"nitrofurantoin", "macrobid"}), 7.0),
    _AntibioticRule("penicillin", frozenset({"penicillin"}), 10.0),
    _AntibioticRule("piperacillin", frozenset({"piperacillin", "zosyn"}), 14.0),
    _AntibioticRule(
        "trimethoprim", frozenset({"trimethoprim", "bactrim", "sulfamethoxazole"}), 10.0
    ),
    _AntibioticRule("vancomycin", frozenset({"vancomycin", "vancocin"}), 14.0),
)


class AntibioticDurationStewardshipChecker:
    """Flag antibiotic courses exceeding recommended duration or missing stop dates."""

    def check(
        self,
        medications: list[Medication],
        days_on_therapy: int | None = None,
        *,
        stop_date_provided: bool = False,
        indication_type: str | None = None,
    ) -> list[AntibioticDurationRisk]:
        """Return duration-stewardship findings for active antibiotics.

        Args:
            medications: Active patient medications.
            days_on_therapy: Days the patient has been on antibiotic therapy, or
                None when unknown. When None, no findings are returned.
            stop_date_provided: Whether a stop date / end-of-course date is
                documented for the antibiotic course.
            indication_type: Optional indication category (e.g. ``uti``,
                ``pneumonia``, ``skin``) to select a recommended maximum
                duration. When omitted, each agent's default maximum applies.

        Returns:
            Advisory :class:`AntibioticDurationRisk` records ordered by
            descending severity, finding kind, then medication name.
        """
        if days_on_therapy is None:
            logger.info("antibiotic_duration_checked", findings=0, eligible=False)
            return []

        recommended_max = self._recommended_max_days(indication_type)
        findings: list[AntibioticDurationRisk] = []
        medication_names_seen: set[str] = set()

        for medication in medications:
            if medication.name in medication_names_seen:
                continue
            match = self._match_antibiotic(medication.name)
            if match is None:
                continue
            medication_names_seen.add(medication.name)
            agent, agent_max_days = match
            effective_max = (
                min(recommended_max, agent_max_days) if indication_type else agent_max_days
            )

            if days_on_therapy > effective_max:
                findings.append(
                    AntibioticDurationRisk(
                        medication=medication.name,
                        agent=agent,
                        finding_kind="exceeds_recommended_duration",
                        severity=self._excess_severity(days_on_therapy, effective_max),
                        days_on_therapy=days_on_therapy,
                        recommended_max_days=effective_max,
                        stop_date_provided=stop_date_provided,
                        indication_type=indication_type,
                        rationale=self._build_excess_rationale(
                            medication_name=medication.name,
                            agent=agent,
                            days_on_therapy=days_on_therapy,
                            effective_max=effective_max,
                            indication_type=indication_type,
                        ),
                    )
                )
            elif not stop_date_provided and days_on_therapy >= _MISSING_STOP_DATE_MIN_DAYS:
                findings.append(
                    AntibioticDurationRisk(
                        medication=medication.name,
                        agent=agent,
                        finding_kind="missing_stop_date",
                        severity=Severity.MODERATE,
                        days_on_therapy=days_on_therapy,
                        recommended_max_days=effective_max,
                        stop_date_provided=stop_date_provided,
                        indication_type=indication_type,
                        rationale=self._build_missing_stop_rationale(
                            medication_name=medication.name,
                            agent=agent,
                            days_on_therapy=days_on_therapy,
                            effective_max=effective_max,
                        ),
                    )
                )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.finding_kind,
                finding.medication.lower(),
            )
        )
        logger.info("antibiotic_duration_checked", findings=len(findings))
        return findings

    @staticmethod
    def _recommended_max_days(indication_type: str | None) -> float:
        """Return the recommended maximum duration for an indication type."""
        if indication_type is None:
            return _DEFAULT_MAX_DURATION_DAYS
        normalized = indication_type.strip().lower().replace(" ", "_")
        return _INDICATION_DURATIONS.get(normalized, _DEFAULT_MAX_DURATION_DAYS)

    @classmethod
    def _match_antibiotic(cls, medication_name: str) -> tuple[str, float] | None:
        """Return matched canonical agent and default max duration."""
        tokens = cls._tokens(medication_name)
        for rule in _ANTIBIOTIC_PANEL:
            if tokens & rule.aliases:
                return rule.agent, rule.default_max_days
        return None

    @staticmethod
    def _excess_severity(days_on_therapy: int, effective_max: float) -> Severity:
        """Map duration excess to severity."""
        if days_on_therapy > effective_max * 2:
            return Severity.HIGH
        return Severity.MODERATE

    @staticmethod
    def _build_excess_rationale(
        *,
        medication_name: str,
        agent: str,
        days_on_therapy: int,
        effective_max: float,
        indication_type: str | None,
    ) -> str:
        """Compose a RESEARCH USE ONLY exceeds-duration rationale."""
        indication_phrase = f" for {indication_type}" if indication_type else ""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{medication_name}' contains {agent}; the patient has been on "
            f"antibiotic therapy for {days_on_therapy} day(s){indication_phrase}, exceeding "
            f"the recommended maximum of {effective_max:g} day(s). Prolonged courses increase "
            "resistance pressure, adverse effects, and C. difficile risk. Review indication, "
            "culture results, and de-escalation or stop date with a qualified clinician."
        )

    @staticmethod
    def _build_missing_stop_rationale(
        *,
        medication_name: str,
        agent: str,
        days_on_therapy: int,
        effective_max: float,
    ) -> str:
        """Compose a RESEARCH USE ONLY missing-stop-date rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{medication_name}' contains {agent}; the patient has been on "
            f"antibiotic therapy for {days_on_therapy} day(s) but no stop date is documented "
            f"(recommended maximum {effective_max:g} day(s)). Document an end-of-course date "
            "or duration to support stewardship review and timely de-escalation."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
