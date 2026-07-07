"""Pregnancy-safety checker.

A patient's active medication list may contain agents that are established human
teratogens or otherwise contraindicated in pregnancy (for example isotretinoin,
warfarin, methotrexate, valproate, or ACE inhibitors). Neither the drug-drug
interaction checker nor the drug-allergy checker surfaces this risk, because the
hazard is to the fetus rather than an interaction or an allergy.

This checker flags each active medication that matches a known teratogenic agent,
but only when the patient is documented as pregnant — so it never raises noise for
non-pregnant patients. It uses whole-token matching (never loose substrings) and a
conservative, well-established agent list. It is deterministic and RESEARCH USE
ONLY, complementing the drug-drug interaction, drug-allergy, and duplicate-therapy
checkers.
"""

from __future__ import annotations

import re

from medagent.logging_config import get_logger
from medagent.models import Medication, PregnancyRisk, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical teratogenic agent token -> (severity, short rationale). Agents are
# matched as whole component tokens of a medication name.
_TERATOGENIC_AGENTS: dict[str, tuple[Severity, str]] = {
    "isotretinoin": (Severity.CRITICAL, "a potent teratogen causing severe congenital defects"),
    "thalidomide": (Severity.CRITICAL, "a potent teratogen causing severe limb defects"),
    "methotrexate": (Severity.CRITICAL, "an abortifacient teratogen contraindicated in pregnancy"),
    "misoprostol": (Severity.CRITICAL, "an abortifacient contraindicated in ongoing pregnancy"),
    "warfarin": (Severity.HIGH, "associated with fetal warfarin syndrome"),
    "valproate": (Severity.HIGH, "associated with neural-tube and neurodevelopmental defects"),
    "valproic": (Severity.HIGH, "valproic acid is associated with neural-tube defects"),
    "phenytoin": (Severity.HIGH, "associated with fetal hydantoin syndrome"),
    "carbamazepine": (Severity.HIGH, "associated with neural-tube defects"),
    "lithium": (Severity.HIGH, "associated with cardiac (Ebstein) anomalies"),
    "methimazole": (Severity.HIGH, "associated with aplasia cutis and choanal atresia"),
    # ACE inhibitors — fetal renal and skull defects, especially 2nd/3rd trimester.
    "lisinopril": (Severity.HIGH, "an ACE inhibitor causing fetal renopathy"),
    "enalapril": (Severity.HIGH, "an ACE inhibitor causing fetal renopathy"),
    "ramipril": (Severity.HIGH, "an ACE inhibitor causing fetal renopathy"),
    "captopril": (Severity.HIGH, "an ACE inhibitor causing fetal renopathy"),
    # ARBs — same fetal renal risk as ACE inhibitors.
    "losartan": (Severity.HIGH, "an ARB causing fetal renopathy"),
    "valsartan": (Severity.HIGH, "an ARB causing fetal renopathy"),
    "irbesartan": (Severity.HIGH, "an ARB causing fetal renopathy"),
    # Tetracyclines — dental staining and impaired bone growth.
    "tetracycline": (Severity.MODERATE, "causes fetal dental staining and bone-growth effects"),
    "doxycycline": (Severity.MODERATE, "causes fetal dental staining and bone-growth effects"),
    "minocycline": (Severity.MODERATE, "causes fetal dental staining and bone-growth effects"),
}


class PregnancySafetyChecker:
    """Flag active medications that are unsafe to use during pregnancy."""

    def check(self, medications: list[Medication], pregnant: bool) -> list[PregnancyRisk]:
        """Return one finding per medication that matches a teratogenic agent.

        Args:
            medications: Active patient medications.
            pregnant: Whether the patient is documented as pregnant. When
                ``False`` the checker returns no findings, since the risk applies
                only during pregnancy.

        Returns:
            One :class:`PregnancyRisk` per medication matching a teratogenic
            agent, ordered by descending severity then medication name. When a
            medication matches more than one agent, the highest-severity agent is
            reported.
        """
        if not pregnant:
            return []

        findings: list[PregnancyRisk] = []
        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue
            matched = [
                (agent, *_TERATOGENIC_AGENTS[agent]) for agent in tokens & set(_TERATOGENIC_AGENTS)
            ]
            if not matched:
                continue
            agent, severity, reason = max(
                matched, key=lambda item: (_SEVERITY_RANK[item[1]], item[0])
            )
            findings.append(
                PregnancyRisk(
                    medication=medication.name,
                    agent=agent,
                    severity=severity,
                    rationale=(
                        f"Medication '{medication.name}' contains {agent}, which is {reason}; "
                        "review before use in a pregnant patient."
                    ),
                )
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.medication))
        logger.info("pregnancy_safety_checked", findings=len(findings))
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
