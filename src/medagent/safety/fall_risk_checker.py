"""Fall-risk medication safety checker for older adults.

Several medication classes increase fall and fracture risk in adults aged 65
and older through sedation, orthostasis, anticholinergic effects, or impaired
balance and reaction time. These hazards are distinct from general Beers
Criteria PIM flagging, anticholinergic-burden scoring, geriatric deprescribing
opportunity detection, and STOPP/START indication-conditioned rules — this
checker focuses specifically on fall-risk mechanisms.

The check is gated on ``patient_age >= 65``. It uses a small, conservative
RESEARCH USE ONLY panel and whole-token matching. Findings are advisory and
never modify a medication list.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import FallRiskFinding, Medication, Severity

logger = get_logger(__name__)

# Fall-risk education commonly focuses on adults aged 65 and older.
_OLDER_ADULT_AGE_THRESHOLD: Final[int] = 65

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical fall-risk agent token -> (risk_category, severity, concern descriptor).
# Agents are matched as whole component tokens of a medication name.
_FALL_RISK_AGENTS: dict[str, tuple[str, Severity, str]] = {
    # Benzodiazepines — sedation, impaired balance, fracture risk.
    "alprazolam": ("benzodiazepine", Severity.HIGH, "sedation and impaired balance"),
    "lorazepam": ("benzodiazepine", Severity.HIGH, "sedation and impaired balance"),
    "diazepam": ("benzodiazepine", Severity.HIGH, "prolonged sedation and fracture risk"),
    "clonazepam": ("benzodiazepine", Severity.HIGH, "sedation and impaired balance"),
    "temazepam": ("benzodiazepine", Severity.HIGH, "night-time sedation and falls"),
    "chlordiazepoxide": ("benzodiazepine", Severity.HIGH, "prolonged sedation and fracture risk"),
    "flurazepam": ("benzodiazepine", Severity.HIGH, "prolonged sedation and fracture risk"),
    "oxazepam": ("benzodiazepine", Severity.HIGH, "sedation and impaired balance"),
    # Non-benzodiazepine Z-drug hypnotics.
    "zolpidem": ("z-drug hypnotic", Severity.HIGH, "next-day sedation and nocturnal falls"),
    "zaleplon": ("z-drug hypnotic", Severity.MODERATE, "nocturnal confusion and falls"),
    "eszopiclone": ("z-drug hypnotic", Severity.HIGH, "next-day sedation and nocturnal falls"),
    # Anticholinergic subset with strong fall association.
    "diphenhydramine": (
        "anticholinergic",
        Severity.MODERATE,
        "sedation, confusion, and impaired balance",
    ),
    "hydroxyzine": (
        "anticholinergic",
        Severity.MODERATE,
        "sedation, confusion, and impaired balance",
    ),
    "oxybutynin": (
        "anticholinergic",
        Severity.MODERATE,
        "confusion and impaired gait from anticholinergic load",
    ),
    "tolterodine": (
        "anticholinergic",
        Severity.MODERATE,
        "confusion and impaired gait from anticholinergic load",
    ),
    "amitriptyline": (
        "anticholinergic",
        Severity.HIGH,
        "strong anticholinergic sedation and orthostasis",
    ),
    "doxepin": (
        "anticholinergic",
        Severity.HIGH,
        "strong anticholinergic sedation and orthostasis",
    ),
    # Antipsychotics — sedation, extrapyramidal effects, orthostasis.
    "haloperidol": ("antipsychotic", Severity.HIGH, "sedation, EPS, and orthostatic hypotension"),
    "risperidone": ("antipsychotic", Severity.HIGH, "sedation, EPS, and orthostatic hypotension"),
    "olanzapine": ("antipsychotic", Severity.HIGH, "sedation and orthostatic hypotension"),
    "quetiapine": ("antipsychotic", Severity.HIGH, "sedation and orthostatic hypotension"),
    # Skeletal muscle relaxants.
    "cyclobenzaprine": (
        "muscle relaxant",
        Severity.MODERATE,
        "sedation, weakness, and anticholinergic effects",
    ),
    "carisoprodol": ("muscle relaxant", Severity.HIGH, "sedation, weakness, and dependence"),
    "methocarbamol": ("muscle relaxant", Severity.MODERATE, "sedation and muscle weakness"),
    # Peripheral alpha-1 blockers (orthostatic hypotension → falls).
    "doxazosin": (
        "alpha-1 blocker",
        Severity.MODERATE,
        "orthostatic hypotension precipitating falls",
    ),
    "prazosin": (
        "alpha-1 blocker",
        Severity.MODERATE,
        "orthostatic hypotension precipitating falls",
    ),
    "terazosin": (
        "alpha-1 blocker",
        Severity.MODERATE,
        "orthostatic hypotension precipitating falls",
    ),
}


class FallRiskChecker:
    """Flag medications that increase fall risk in older adults."""

    def check(
        self, medications: list[Medication], patient_age: int | None
    ) -> list[FallRiskFinding]:
        """Return fall-risk findings for an older adult's active medications.

        Args:
            medications: Active patient medications.
            patient_age: Patient age in years, or None when unknown. Findings are
                returned only when ``patient_age >= 65``.

        Returns:
            One :class:`FallRiskFinding` per matching medication, ordered by
            descending severity then medication name. When a medication matches
            more than one fall-risk agent, the alphabetically first agent is used.
            An empty list is returned for patients under 65, unknown age, or when
            no medication is on the curated fall-risk panel.
        """
        if patient_age is None or patient_age < _OLDER_ADULT_AGE_THRESHOLD:
            logger.info("fall_risk_checked", findings=0, eligible=False)
            return []

        findings: list[FallRiskFinding] = []
        for medication in medications:
            tokens = self._tokens(medication.name)
            matched_agents = sorted(tokens & set(_FALL_RISK_AGENTS))
            if not matched_agents:
                continue
            agent = matched_agents[0]
            risk_category, severity, concern = _FALL_RISK_AGENTS[agent]
            findings.append(
                FallRiskFinding(
                    medication=medication.name,
                    agent=agent,
                    risk_category=risk_category,
                    severity=severity,
                    patient_age=patient_age,
                    rationale=(
                        "RESEARCH USE ONLY: "
                        f"Medication '{medication.name}' contains {agent}, a "
                        f"{risk_category} associated with increased fall risk in adults aged "
                        f"{_OLDER_ADULT_AGE_THRESHOLD} and older (patient age {patient_age}). "
                        f"Primary mechanism: {concern}. Review indication, dose, timing, "
                        "and fall-prevention measures with a qualified clinician before any "
                        "medication change."
                    ),
                )
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.medication))
        logger.info("fall_risk_checked", findings=len(findings), eligible=True)
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
