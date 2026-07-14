"""Hepatic-dose (Child-Pugh) safety checker.

Many widely prescribed drugs are metabolised by the liver or are intrinsically
hepatotoxic, so in reduced hepatic function they accumulate, precipitate
encephalopathy or bleeding, or accelerate liver injury unless the dose is
reduced or the drug is avoided. This hazard is neither a drug-drug interaction,
an allergy, a duplicate therapy, a pregnancy risk, a QT/serotonin/anticholinergic
burden, an age-conditioned Beers judgement, nor a *renal*-function judgement — it
is a *hepatic-function-conditioned, single-agent* appropriateness judgement keyed
on the patient's Child-Pugh class, so it is not surfaced by the existing checkers
and complements the renal-dose (eGFR) checker.

This checker applies only when hepatic function is known and impaired; with an
unknown or normal hepatic function it returns no findings. For a known impaired
hepatic function it flags each active medication that matches a hepatically-risky
agent whose impairment threshold the patient meets or exceeds, using whole-token
matching (never loose substrings). It is deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re

from medagent.logging_config import get_logger
from medagent.models import HepaticDoseRisk, HepaticFunction, Medication, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Ordinal severity of hepatic impairment (Child-Pugh). A medication is flagged
# when the patient's impairment level is at or above the agent's threshold level.
_FUNCTION_RANK: dict[HepaticFunction, int] = {
    HepaticFunction.NORMAL: 0,
    HepaticFunction.MILD: 1,
    HepaticFunction.MODERATE: 2,
    HepaticFunction.SEVERE: 3,
}

# Canonical hepatic agent token -> (threshold hepatic-function class, severity,
# action, concern). A medication is flagged when the patient's hepatic-function
# class is at or above the threshold. Agents are matched as whole component
# tokens of a medication name.
_HEPATIC_AGENTS: dict[str, tuple[HepaticFunction, Severity, str, str]] = {
    # Intrinsically hepatotoxic — avoid in established impairment.
    "methotrexate": (
        HepaticFunction.MODERATE,
        Severity.HIGH,
        "avoid",
        "hepatotoxicity and fibrosis",
    ),
    "isoniazid": (HepaticFunction.MODERATE, Severity.HIGH, "avoid", "hepatotoxicity"),
    "amiodarone": (HepaticFunction.MODERATE, Severity.HIGH, "avoid", "hepatotoxicity"),
    "valproate": (HepaticFunction.MODERATE, Severity.HIGH, "avoid", "hepatotoxicity"),
    "valproic": (HepaticFunction.MODERATE, Severity.HIGH, "avoid", "hepatotoxicity"),
    "ketoconazole": (HepaticFunction.MILD, Severity.HIGH, "avoid", "hepatotoxicity"),
    "rifampicin": (HepaticFunction.MODERATE, Severity.HIGH, "avoid", "hepatotoxicity"),
    "rifampin": (HepaticFunction.MODERATE, Severity.HIGH, "avoid", "hepatotoxicity"),
    "nimesulide": (HepaticFunction.MILD, Severity.HIGH, "avoid", "hepatotoxicity"),
    # Statins — avoid in active/decompensated liver disease.
    "simvastatin": (HepaticFunction.SEVERE, Severity.HIGH, "avoid", "active liver disease"),
    "atorvastatin": (HepaticFunction.SEVERE, Severity.HIGH, "avoid", "active liver disease"),
    "lovastatin": (HepaticFunction.SEVERE, Severity.HIGH, "avoid", "active liver disease"),
    # NSAIDs — avoid in cirrhosis (GI bleeding, hepatorenal syndrome, fluid retention).
    "ibuprofen": (
        HepaticFunction.MODERATE,
        Severity.HIGH,
        "avoid",
        "bleeding and hepatorenal risk",
    ),
    "naproxen": (HepaticFunction.MODERATE, Severity.HIGH, "avoid", "bleeding and hepatorenal risk"),
    "diclofenac": (
        HepaticFunction.MODERATE,
        Severity.HIGH,
        "avoid",
        "bleeding and hepatorenal risk",
    ),
    "ketorolac": (
        HepaticFunction.MODERATE,
        Severity.HIGH,
        "avoid",
        "bleeding and hepatorenal risk",
    ),
    "indomethacin": (
        HepaticFunction.MODERATE,
        Severity.HIGH,
        "avoid",
        "bleeding and hepatorenal risk",
    ),
    # Direct oral anticoagulants — coagulopathy/bleeding risk in Child-Pugh B-C.
    "rivaroxaban": (
        HepaticFunction.MODERATE,
        Severity.HIGH,
        "avoid",
        "coagulopathy and bleeding risk",
    ),
    "apixaban": (HepaticFunction.SEVERE, Severity.HIGH, "avoid", "coagulopathy and bleeding risk"),
    # Sedatives/opioids — precipitate hepatic encephalopathy or accumulate.
    "diazepam": (
        HepaticFunction.MODERATE,
        Severity.MODERATE,
        "avoid",
        "precipitation of hepatic encephalopathy",
    ),
    "chlordiazepoxide": (
        HepaticFunction.MODERATE,
        Severity.MODERATE,
        "avoid",
        "precipitation of hepatic encephalopathy",
    ),
    "midazolam": (
        HepaticFunction.MODERATE,
        Severity.MODERATE,
        "reduce dose",
        "prolonged sedation and encephalopathy risk",
    ),
    "morphine": (
        HepaticFunction.MODERATE,
        Severity.MODERATE,
        "reduce dose",
        "accumulation and encephalopathy risk",
    ),
    "codeine": (
        HepaticFunction.MODERATE,
        Severity.MODERATE,
        "avoid",
        "impaired activation and encephalopathy risk",
    ),
    "tramadol": (
        HepaticFunction.MODERATE,
        Severity.MODERATE,
        "reduce dose",
        "accumulation and encephalopathy risk",
    ),
    # Analgesic — dose-limit in decompensated disease.
    "acetaminophen": (
        HepaticFunction.SEVERE,
        Severity.MODERATE,
        "reduce dose",
        "dose-dependent hepatotoxicity; limit total daily dose",
    ),
    "paracetamol": (
        HepaticFunction.SEVERE,
        Severity.MODERATE,
        "reduce dose",
        "dose-dependent hepatotoxicity; limit total daily dose",
    ),
}


class HepaticDoseChecker:
    """Flag hepatically-risky medications inappropriate for a patient's liver function."""

    def check(
        self, medications: list[Medication], hepatic_function: HepaticFunction | None
    ) -> list[HepaticDoseRisk]:
        """Return hepatic-dose findings for a patient's active medications.

        A finding is produced only when hepatic function is known and impaired
        (``MILD``/``MODERATE``/``SEVERE``) and the patient's impairment class is
        at or above a matching agent's threshold. With an unknown or ``NORMAL``
        hepatic function no finding is returned.

        Args:
            medications: Active patient medications.
            hepatic_function: Patient hepatic-function class (Child-Pugh), or
                None when unknown.

        Returns:
            One :class:`HepaticDoseRisk` per matching medication, ordered by
            descending severity then medication name. When a medication matches
            more than one triggered agent, the highest-severity agent (then the
            alphabetically first) is reported. An empty list is returned when
            hepatic function is unknown or normal, or no medication is affected
            at that impairment level.
        """
        if hepatic_function is None or hepatic_function is HepaticFunction.NORMAL:
            logger.info("hepatic_dose_checked", findings=0, eligible=False)
            return []

        patient_level = _FUNCTION_RANK[hepatic_function]
        findings: list[HepaticDoseRisk] = []
        for medication in medications:
            tokens = self._tokens(medication.name)
            triggered = [
                agent
                for agent in tokens & set(_HEPATIC_AGENTS)
                if patient_level >= _FUNCTION_RANK[_HEPATIC_AGENTS[agent][0]]
            ]
            if not triggered:
                continue
            agent = min(
                triggered,
                key=lambda item: (-_SEVERITY_RANK[_HEPATIC_AGENTS[item][1]], item),
            )
            threshold, severity, action, concern = _HEPATIC_AGENTS[agent]
            rationale = (
                f"Medication '{medication.name}' contains {agent}, which is hepatically "
                f"cleared or hepatotoxic; at {hepatic_function.value} hepatic impairment "
                f"(threshold {threshold.value}) the recommendation is to {action} because of "
                f"{concern}. Review the dose against hepatic function."
            )
            findings.append(
                HepaticDoseRisk(
                    medication=medication.name,
                    agent=agent,
                    hepatic_function=hepatic_function,
                    threshold_function=threshold,
                    action=action,
                    severity=severity,
                    rationale=rationale,
                )
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.medication))
        logger.info("hepatic_dose_checked", findings=len(findings), eligible=True)
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
