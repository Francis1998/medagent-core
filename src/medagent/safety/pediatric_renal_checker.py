"""Pediatric renal dosing safety checker.

Renally-cleared medications in pediatric patients require age-appropriate renal
function assessment (eGFR or CrCl) before dosing. The adult renal-dose checker
flags agents when eGFR is known and below a threshold, but it does not address
the distinct pediatric hazard of *missing* renal function data or values below
age-adjusted norms in children. This checker complements `renal_dose_checker.py`
and `pediatric_dose_checker.py` by focusing on renally-cleared agents in
patients under 18 years.

It flags renally-cleared medications when eGFR and CrCl are both missing, or when
the available renal function value falls below an age-adjusted threshold.
Whole-token matching is used throughout. Findings are deterministic and RESEARCH
USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, PediatricRenalRisk, Severity

logger = get_logger(__name__)

_PEDIATRIC_AGE_MAX_YEARS: Final[float] = 18.0

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical renally-cleared pediatric agent -> (base eGFR/CrCl threshold, severity, concern).
_RENAL_AGENTS: Final[dict[str, tuple[float, Severity, str]]] = {
    "gentamicin": (60.0, Severity.HIGH, "aminoglycoside accumulation and nephrotoxicity"),
    "tobramycin": (60.0, Severity.HIGH, "aminoglycoside accumulation and nephrotoxicity"),
    "amikacin": (60.0, Severity.HIGH, "aminoglycoside accumulation and nephrotoxicity"),
    "vancomycin": (60.0, Severity.HIGH, "accumulation and nephrotoxicity"),
    "acyclovir": (50.0, Severity.HIGH, "accumulation and neurotoxicity"),
    "ganciclovir": (50.0, Severity.HIGH, "accumulation and myelosuppression"),
    "metformin": (45.0, Severity.HIGH, "lactic acidosis risk"),
    "nitrofurantoin": (40.0, Severity.HIGH, "ineffective and increased toxicity"),
    "gabapentin": (60.0, Severity.MODERATE, "accumulation causing sedation/ataxia"),
    "pregabalin": (60.0, Severity.MODERATE, "accumulation causing sedation"),
    "enoxaparin": (50.0, Severity.HIGH, "anti-Xa accumulation and bleeding"),
    "cefepime": (50.0, Severity.MODERATE, "neurotoxicity from accumulation"),
    "ceftazidime": (50.0, Severity.MODERATE, "accumulation risk"),
    "amoxicillin": (30.0, Severity.MODERATE, "dose adjustment may be required"),
    "cephalexin": (30.0, Severity.MODERATE, "dose adjustment may be required"),
}

# Brand / synonym tokens that canonicalize to a panel agent.
_AGENT_ALIASES: Final[dict[str, str]] = {
    "keflex": "cephalexin",
    "vancocin": "vancomycin",
}


class PediatricRenalDosingChecker:
    """Flag renally-cleared medications in pediatric patients with inadequate renal data."""

    def check(
        self,
        medications: list[Medication],
        age_years: float | None,
        egfr: float | None = None,
        crcl: float | None = None,
    ) -> list[PediatricRenalRisk]:
        """Return findings for renally-cleared meds in pediatric patients.

        Args:
            medications: Active patient medications.
            age_years: Patient age in years, or None when unknown. Findings are
                returned only for patients strictly younger than 18 years.
            egfr: Estimated GFR in mL/min/1.73m², or None when unknown.
            crcl: Creatinine clearance in mL/min, or None when unknown.

        Returns:
            One :class:`PediatricRenalRisk` per matching medication when renal
            function is missing or below the age-adjusted threshold, ordered by
            descending severity then medication name.
        """
        if age_years is None or age_years >= _PEDIATRIC_AGE_MAX_YEARS:
            logger.info("pediatric_renal_checked", findings=0, eligible=False)
            return []

        renal_value = egfr if egfr is not None else crcl
        renal_measure = "eGFR" if egfr is not None else "CrCl" if crcl is not None else None
        age_threshold = self._age_adjusted_threshold(age_years)
        missing_renal = egfr is None and crcl is None
        below_threshold = renal_value is not None and renal_value < age_threshold

        findings: list[PediatricRenalRisk] = []
        for medication in medications:
            match = self._match_agent(medication.name)
            if match is None:
                continue
            agent, base_threshold, baseline_severity, concern = match
            effective_threshold = max(base_threshold, age_threshold)

            if missing_renal:
                findings.append(
                    PediatricRenalRisk(
                        medication=medication.name,
                        agent=agent,
                        finding_kind="missing_renal_function",
                        severity=baseline_severity,
                        age_years=age_years,
                        egfr=egfr,
                        crcl=crcl,
                        age_adjusted_threshold=effective_threshold,
                        concern=concern,
                        rationale=self._build_missing_rationale(
                            medication_name=medication.name,
                            agent=agent,
                            age_years=age_years,
                            concern=concern,
                        ),
                    )
                )
            elif below_threshold and renal_value is not None and renal_measure is not None:
                findings.append(
                    PediatricRenalRisk(
                        medication=medication.name,
                        agent=agent,
                        finding_kind="below_renal_threshold",
                        severity=self._elevated_severity(
                            baseline_severity, renal_value, effective_threshold
                        ),
                        age_years=age_years,
                        egfr=egfr,
                        crcl=crcl,
                        age_adjusted_threshold=effective_threshold,
                        concern=concern,
                        rationale=self._build_below_threshold_rationale(
                            medication_name=medication.name,
                            agent=agent,
                            age_years=age_years,
                            renal_measure=renal_measure,
                            renal_value=renal_value,
                            effective_threshold=effective_threshold,
                            concern=concern,
                        ),
                    )
                )

        findings.sort(
            key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.medication.lower())
        )
        logger.info(
            "pediatric_renal_checked",
            findings=len(findings),
            missing_renal=missing_renal,
            below_threshold=below_threshold,
        )
        return findings

    def _match_agent(self, medication_name: str) -> tuple[str, float, Severity, str] | None:
        """Return matched canonical agent, threshold, severity, and concern."""
        tokens = self._tokens(medication_name)
        if not tokens:
            return None

        canonical_agents: set[str] = set()
        for token in tokens:
            if token in _RENAL_AGENTS:
                canonical_agents.add(token)
            elif token in _AGENT_ALIASES:
                canonical_agents.add(_AGENT_ALIASES[token])

        if not canonical_agents:
            return None

        agent = sorted(canonical_agents)[0]
        threshold, severity, concern = _RENAL_AGENTS[agent]
        return agent, threshold, severity, concern

    @staticmethod
    def _age_adjusted_threshold(age_years: float) -> float:
        """Return the minimum acceptable eGFR/CrCl for a pediatric age band."""
        if age_years < 2.0:
            return 90.0
        if age_years < 12.0:
            return 75.0
        return 60.0

    @staticmethod
    def _elevated_severity(baseline: Severity, renal_value: float, threshold: float) -> Severity:
        """Elevate severity when renal function is markedly below threshold."""
        if renal_value < threshold * 0.5:
            return Severity.CRITICAL
        if baseline == Severity.MODERATE:
            return Severity.HIGH
        return baseline

    @staticmethod
    def _build_missing_rationale(
        *,
        medication_name: str,
        agent: str,
        age_years: float,
        concern: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY missing-renal-function rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{medication_name}' contains {agent}, a renally-cleared agent "
            f"in a pediatric patient ({age_years:g} years). No eGFR or CrCl is documented; "
            f"renal function assessment is needed before dosing to avoid {concern}. "
            "Obtain age-appropriate renal function and review dosing with a qualified clinician."
        )

    @staticmethod
    def _build_below_threshold_rationale(
        *,
        medication_name: str,
        agent: str,
        age_years: float,
        renal_measure: str,
        renal_value: float,
        effective_threshold: float,
        concern: str,
    ) -> str:
        """Compose a RESEARCH USE ONLY below-threshold rationale."""
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{medication_name}' contains {agent}, a renally-cleared agent "
            f"in a pediatric patient ({age_years:g} years). Documented {renal_measure} "
            f"is {renal_value:g} (below the age-adjusted threshold of "
            f"{effective_threshold:g}), raising risk of {concern}. Review dose adjustment "
            "or alternative therapy with a qualified clinician."
        )

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
