"""FDA black-box (boxed) warning safety checker.

An FDA *boxed warning* (commonly called a black-box warning) is the agency's
strongest labelling caution for a marketed drug — for example fluoroquinolone
tendinopathy / neuropathy risk, clozapine agranulocytosis, or isotretinoin
teratogenicity. This hazard is neither a drug–drug interaction, an allergy, a
duplicate-therapy flag, a pregnancy-gated teratogen screen alone, a
QT/serotonin/anticholinergic burden, an age-conditioned Beers/STOPP judgement,
nor a renal/hepatic dose judgement: it is a *labelling-severity* judgement keyed
on agents that carry an FDA boxed warning, so it is not surfaced by the existing
checkers.

This checker matches active medications to a conservative curated panel of
agents with well-known boxed warnings (whole-token matching, never loose
substrings) and emits one finding per matched agent. It is deterministic and
RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import BlackBoxWarningRisk, Medication, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical agent token -> (warning theme, severity, short clinical concern).
# Agents are matched as whole component tokens of a medication name.
_BOXED_WARNING_AGENTS: Final[dict[str, tuple[str, Severity, str]]] = {
    # Fluoroquinolones — tendinopathy, peripheral neuropathy, CNS effects.
    "ciprofloxacin": (
        "fluoroquinolone",
        Severity.HIGH,
        "tendinopathy, peripheral neuropathy, and CNS adverse effects",
    ),
    "levofloxacin": (
        "fluoroquinolone",
        Severity.HIGH,
        "tendinopathy, peripheral neuropathy, and CNS adverse effects",
    ),
    "moxifloxacin": (
        "fluoroquinolone",
        Severity.HIGH,
        "tendinopathy, peripheral neuropathy, and CNS adverse effects",
    ),
    "ofloxacin": (
        "fluoroquinolone",
        Severity.HIGH,
        "tendinopathy, peripheral neuropathy, and CNS adverse effects",
    ),
    # Clozapine — agranulocytosis, myocarditis, seizures, orthostasis.
    "clozapine": (
        "clozapine",
        Severity.CRITICAL,
        "severe neutropenia/agranulocytosis, myocarditis, seizures, and orthostatic hypotension",
    ),
    # Isotretinoin — teratogenicity.
    "isotretinoin": (
        "retinoid",
        Severity.CRITICAL,
        "severe teratogenicity (iPLEDGE / pregnancy prevention required)",
    ),
    # Methotrexate — embryo-fetal toxicity, bone marrow, liver, lung, infection.
    "methotrexate": (
        "antimetabolite",
        Severity.CRITICAL,
        "embryo-fetal toxicity, myelosuppression, hepatotoxicity, and pneumonitis",
    ),
    # Warfarin — major bleeding.
    "warfarin": (
        "vitamin K antagonist",
        Severity.HIGH,
        "major or fatal bleeding",
    ),
    # Metformin — lactic acidosis.
    "metformin": (
        "biguanide",
        Severity.HIGH,
        "lactic acidosis (especially with renal/hepatic impairment or hypoxia)",
    ),
    # Amiodarone — pulmonary, hepatic, and proarrhythmic toxicity.
    "amiodarone": (
        "class III antiarrhythmic",
        Severity.CRITICAL,
        "pulmonary toxicity, hepatotoxicity, and worsened arrhythmia",
    ),
    # Valproate / valproic acid — hepatotoxicity, teratogenicity, pancreatitis.
    "valproate": (
        "antiepileptic",
        Severity.CRITICAL,
        "hepatotoxicity, teratogenicity, and pancreatitis",
    ),
    "valproic": (
        "antiepileptic",
        Severity.CRITICAL,
        "hepatotoxicity, teratogenicity, and pancreatitis",
    ),
    # Carbamazepine — serious dermatologic reactions (SJS/TEN), aplastic anemia.
    "carbamazepine": (
        "antiepileptic",
        Severity.HIGH,
        "serious dermatologic reactions (SJS/TEN) and aplastic anemia/agranulocytosis",
    ),
    # Opioid analgesics — addiction, abuse, misuse, respiratory depression.
    "fentanyl": (
        "opioid analgesic",
        Severity.CRITICAL,
        "addiction, abuse, misuse, and life-threatening respiratory depression",
    ),
    "oxycodone": (
        "opioid analgesic",
        Severity.HIGH,
        "addiction, abuse, misuse, and life-threatening respiratory depression",
    ),
    "hydrocodone": (
        "opioid analgesic",
        Severity.HIGH,
        "addiction, abuse, misuse, and life-threatening respiratory depression",
    ),
    "morphine": (
        "opioid analgesic",
        Severity.HIGH,
        "addiction, abuse, misuse, and life-threatening respiratory depression",
    ),
    "hydromorphone": (
        "opioid analgesic",
        Severity.HIGH,
        "addiction, abuse, misuse, and life-threatening respiratory depression",
    ),
    "methadone": (
        "opioid analgesic",
        Severity.CRITICAL,
        "addiction, QT prolongation, and life-threatening respiratory depression",
    ),
    # NSAIDs — CV thrombotic events and GI bleeding.
    "ibuprofen": (
        "NSAID",
        Severity.MODERATE,
        "cardiovascular thrombotic events and serious GI bleeding/ulceration",
    ),
    "naproxen": (
        "NSAID",
        Severity.MODERATE,
        "cardiovascular thrombotic events and serious GI bleeding/ulceration",
    ),
    "diclofenac": (
        "NSAID",
        Severity.MODERATE,
        "cardiovascular thrombotic events and serious GI bleeding/ulceration",
    ),
    "ketorolac": (
        "NSAID",
        Severity.HIGH,
        "serious GI bleeding, renal risk, and cardiovascular thrombotic events",
    ),
    # Pioglitazone — congestive heart failure.
    "pioglitazone": (
        "thiazolidinedione",
        Severity.HIGH,
        "congestive heart failure",
    ),
    # Rosiglitazone — congestive heart failure / myocardial ischemia labelling.
    "rosiglitazone": (
        "thiazolidinedione",
        Severity.HIGH,
        "congestive heart failure and myocardial ischemia risk",
    ),
}


class BlackBoxWarningChecker:
    """Flag active medications that carry an FDA boxed (black-box) warning."""

    def check(self, medications: list[Medication]) -> list[BlackBoxWarningRisk]:
        """Return boxed-warning findings for active medications.

        Each active medication matching a curated boxed-warning agent yields one
        finding. When a medication name matches more than one panel agent, the
        highest-severity agent is preferred (ties break alphabetically).

        Args:
            medications: Active patient medications.

        Returns:
            One :class:`BlackBoxWarningRisk` per matching medication, ordered by
            descending severity then medication name. An empty list is returned
            when no medication matches the panel.
        """
        findings: list[BlackBoxWarningRisk] = []
        for medication in medications:
            tokens = self._tokens(medication.name)
            matched = sorted(
                tokens & set(_BOXED_WARNING_AGENTS),
                key=lambda agent: (
                    -_SEVERITY_RANK[_BOXED_WARNING_AGENTS[agent][1]],
                    agent,
                ),
            )
            if not matched:
                continue
            agent = matched[0]
            warning_theme, severity, concern = _BOXED_WARNING_AGENTS[agent]
            findings.append(
                BlackBoxWarningRisk(
                    medication=medication.name,
                    agent=agent,
                    warning_theme=warning_theme,
                    severity=severity,
                    rationale=(
                        f"Medication '{medication.name}' contains {agent}, an agent with an FDA "
                        f"boxed (black-box) warning in the {warning_theme} class. Primary concern: "
                        f"{concern}. Review indication, alternatives, and required monitoring."
                    ),
                )
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.medication))
        logger.info("black_box_warning_checked", findings=len(findings))
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
