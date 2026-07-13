"""Renal-dose (eGFR) safety checker.

Many widely prescribed drugs are cleared renally, so in reduced kidney function
they accumulate to toxic concentrations unless the dose is reduced or the drug
is avoided. This hazard is neither a drug-drug interaction, an allergy, a
duplicate therapy, a pregnancy risk, a QT/serotonin/anticholinergic burden, nor
an age-conditioned Beers judgement — it is a *renal-function-conditioned,
single-agent* appropriateness judgement keyed on the patient's estimated
glomerular filtration rate (eGFR), so it is not surfaced by the existing
checkers.

This checker applies only when an eGFR is known; with an unknown eGFR it returns
no findings. For a known eGFR it flags each active medication that matches a
renally-cleared agent whose eGFR threshold the patient is at or below, using
whole-token matching (never loose substrings). It is deterministic and RESEARCH
USE ONLY. eGFR is expressed in mL/min/1.73m^2.
"""

from __future__ import annotations

import re

from medagent.logging_config import get_logger
from medagent.models import Medication, RenalDoseRisk, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical renally-cleared agent token -> (eGFR threshold, severity, action,
# concern). A medication is flagged when the patient eGFR is at or below the
# threshold. Agents are matched as whole component tokens of a medication name.
_RENAL_AGENTS: dict[str, tuple[float, Severity, str, str]] = {
    # Contraindicated / avoid below the threshold (accumulation → serious harm).
    "metformin": (30.0, Severity.HIGH, "avoid", "risk of lactic acidosis"),
    "nitrofurantoin": (30.0, Severity.HIGH, "avoid", "ineffective and increased toxicity"),
    "dabigatran": (30.0, Severity.HIGH, "avoid", "accumulation and major bleeding risk"),
    "fondaparinux": (30.0, Severity.HIGH, "avoid", "accumulation and bleeding risk"),
    "spironolactone": (30.0, Severity.HIGH, "avoid", "life-threatening hyperkalaemia"),
    # NSAIDs (reduced renal perfusion, acute kidney injury).
    "ibuprofen": (30.0, Severity.HIGH, "avoid", "acute kidney injury"),
    "naproxen": (30.0, Severity.HIGH, "avoid", "acute kidney injury"),
    "ketorolac": (30.0, Severity.HIGH, "avoid", "acute kidney injury"),
    "indomethacin": (30.0, Severity.HIGH, "avoid", "acute kidney injury"),
    "diclofenac": (30.0, Severity.HIGH, "avoid", "acute kidney injury"),
    # Dose-reduce below the threshold (accumulation → toxicity).
    "rivaroxaban": (30.0, Severity.MODERATE, "reduce dose", "accumulation and bleeding risk"),
    "apixaban": (30.0, Severity.MODERATE, "reduce dose", "accumulation and bleeding risk"),
    "edoxaban": (30.0, Severity.MODERATE, "reduce dose", "accumulation and bleeding risk"),
    "enoxaparin": (30.0, Severity.MODERATE, "reduce dose", "anti-Xa accumulation and bleeding"),
    "colchicine": (30.0, Severity.MODERATE, "reduce dose", "accumulation and toxicity"),
    "allopurinol": (30.0, Severity.MODERATE, "reduce dose", "oxypurinol accumulation"),
    "digoxin": (50.0, Severity.MODERATE, "reduce dose", "accumulation and toxicity"),
    "atenolol": (35.0, Severity.MODERATE, "reduce dose", "renal accumulation"),
    "gabapentin": (60.0, Severity.MODERATE, "reduce dose", "accumulation causing sedation/ataxia"),
    "pregabalin": (60.0, Severity.MODERATE, "reduce dose", "accumulation causing sedation"),
}


class RenalDoseChecker:
    """Flag renally-cleared medications inappropriate for a patient's eGFR."""

    def check(self, medications: list[Medication], egfr: float | None) -> list[RenalDoseRisk]:
        """Return renal-dose findings for a patient's active medications.

        A finding is produced only when the eGFR is known and at or below a
        matching agent's threshold. With an unknown eGFR no finding is returned.

        Args:
            medications: Active patient medications.
            egfr: Estimated glomerular filtration rate in mL/min/1.73m^2, or
                None when unknown.

        Returns:
            One :class:`RenalDoseRisk` per matching medication, ordered by
            descending severity then medication name. When a medication matches
            more than one triggered agent, the highest-severity agent (then the
            alphabetically first) is reported. An empty list is returned when the
            eGFR is unknown or no medication is affected at that eGFR.
        """
        if egfr is None:
            logger.info("renal_dose_checked", findings=0, eligible=False)
            return []

        findings: list[RenalDoseRisk] = []
        for medication in medications:
            tokens = self._tokens(medication.name)
            triggered = [
                agent for agent in tokens & set(_RENAL_AGENTS) if egfr <= _RENAL_AGENTS[agent][0]
            ]
            if not triggered:
                continue
            agent = min(
                triggered,
                key=lambda item: (-_SEVERITY_RANK[_RENAL_AGENTS[item][1]], item),
            )
            threshold, severity, action, concern = _RENAL_AGENTS[agent]
            rationale = (
                f"Medication '{medication.name}' contains {agent}, which is renally cleared; "
                f"at eGFR {egfr:g} mL/min/1.73m^2 (threshold {threshold:g}) the recommendation "
                f"is to {action} because of {concern}. Review the dose against renal function."
            )
            findings.append(
                RenalDoseRisk(
                    medication=medication.name,
                    agent=agent,
                    egfr=egfr,
                    threshold_egfr=threshold,
                    action=action,
                    severity=severity,
                    rationale=rationale,
                )
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.medication))
        logger.info("renal_dose_checked", findings=len(findings), eligible=True)
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name.

        Args:
            name: Medication name (may contain brand/dose/component separators).

        Returns:
            Set of component tokens.
        """
        return set(re.findall(r"[a-z0-9]+", name.lower()))
