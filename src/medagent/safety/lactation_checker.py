"""Lactation / breastfeeding medication-safety checker.

Some medication hazards are specific to breastfeeding: drug transfer into milk
can expose an infant to toxicity, sedation, marrow suppression, thyroid
ablation, or chemotherapy effects. These risks are distinct from pregnancy,
drug-drug interactions, allergy, duplicate therapy, and age/organ-function
checks.

This checker is gated on a documented ``breastfeeding`` flag. It uses a small,
conservative RESEARCH USE ONLY panel and whole-token / whole-phrase matching
with selected aliases (for example I-131 / radioactive iodine). Findings are
advisory and never modify a medication list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import LactationRisk, Medication, Severity

logger = get_logger(__name__)

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


@dataclass(frozen=True)
class _LactationRule:
    """A curated lactation safety panel entry."""

    agent: str
    aliases: frozenset[tuple[str, ...]]
    concern_category: str
    severity: Severity
    concern: str


_LACTATION_RULES: Final[tuple[_LactationRule, ...]] = (
    _LactationRule(
        agent="radioactive iodine",
        aliases=frozenset(
            {
                ("i", "131"),
                ("iodine", "131"),
                ("radioactive", "iodine"),
                ("radioiodine",),
                ("sodium", "iodide", "i", "131"),
            }
        ),
        concern_category="radioisotope thyroid ablation",
        severity=Severity.CRITICAL,
        concern=(
            "radioiodine can concentrate in breast milk and expose the infant thyroid to radiation"
        ),
    ),
    _LactationRule(
        agent="cyclophosphamide",
        aliases=frozenset({("cyclophosphamide",), ("cytoxan",)}),
        concern_category="antineoplastic chemotherapy",
        severity=Severity.CRITICAL,
        concern="antineoplastic exposure can cause infant marrow suppression and toxicity",
    ),
    _LactationRule(
        agent="doxorubicin",
        aliases=frozenset({("doxorubicin",), ("adriamycin",)}),
        concern_category="antineoplastic chemotherapy",
        severity=Severity.CRITICAL,
        concern="antineoplastic exposure can cause infant marrow suppression and toxicity",
    ),
    _LactationRule(
        agent="methotrexate",
        aliases=frozenset({("methotrexate",), ("mtx",)}),
        concern_category="antimetabolite chemotherapy",
        severity=Severity.CRITICAL,
        concern="antimetabolite exposure may suppress infant marrow and immune function",
    ),
    _LactationRule(
        agent="fluorouracil",
        aliases=frozenset({("fluorouracil",), ("5", "fluorouracil"), ("5", "fu"), ("5fu",)}),
        concern_category="antimetabolite chemotherapy",
        severity=Severity.CRITICAL,
        concern="antimetabolite exposure may suppress infant marrow and immune function",
    ),
    _LactationRule(
        agent="capecitabine",
        aliases=frozenset({("capecitabine",), ("xeloda",)}),
        concern_category="antimetabolite chemotherapy",
        severity=Severity.CRITICAL,
        concern="antimetabolite exposure may suppress infant marrow and immune function",
    ),
    _LactationRule(
        agent="amiodarone",
        aliases=frozenset({("amiodarone",), ("cordarone",), ("pacerone",)}),
        concern_category="infant thyroid and cardiac exposure",
        severity=Severity.HIGH,
        concern=(
            "long half-life and iodine content can expose the infant to thyroid and cardiac risk"
        ),
    ),
    _LactationRule(
        agent="lithium",
        aliases=frozenset({("lithium",)}),
        concern_category="infant serum accumulation",
        severity=Severity.HIGH,
        concern="milk transfer can produce clinically significant infant serum concentrations",
    ),
    _LactationRule(
        agent="codeine",
        aliases=frozenset({("codeine",), ("tylenol", "3"), ("tylenol", "codeine")}),
        concern_category="opioid infant sedation",
        severity=Severity.HIGH,
        concern=(
            "CYP2D6 ultrarapid metabolism can increase morphine exposure and infant sedation or "
            "respiratory depression"
        ),
    ),
    _LactationRule(
        agent="tramadol",
        aliases=frozenset({("tramadol",), ("ultram",)}),
        concern_category="opioid infant sedation",
        severity=Severity.HIGH,
        concern="opioid transfer may cause infant sedation and respiratory depression",
    ),
)


class LactationSafetyChecker:
    """Flag active medications that are unsafe or high-risk during breastfeeding."""

    def check(self, medications: list[Medication], breastfeeding: bool) -> list[LactationRisk]:
        """Return lactation-safety findings for a breastfeeding patient.

        Args:
            medications: Active patient medications.
            breastfeeding: Whether the patient is documented as breastfeeding /
                lactating. When ``False`` the checker returns no findings, since
                the risk applies only during breastfeeding.

        Returns:
            One :class:`LactationRisk` per medication matching the curated
            lactation panel, ordered by descending severity then medication name.
            When one medication matches multiple agents, the highest-severity
            agent is reported.
        """
        if not breastfeeding:
            logger.info("lactation_safety_checked", findings=0, eligible=False)
            return []

        findings: list[LactationRisk] = []
        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue
            matched = sorted(
                self._matching_rules(tokens),
                key=lambda rule: (-_SEVERITY_RANK[rule.severity], rule.agent),
            )
            if not matched:
                continue

            rule = matched[0]
            findings.append(
                LactationRisk(
                    medication=medication.name,
                    agent=rule.agent,
                    concern_category=rule.concern_category,
                    severity=rule.severity,
                    rationale=(
                        "RESEARCH USE ONLY: "
                        f"Medication '{medication.name}' matches {rule.agent}, a lactation "
                        f"safety concern in the '{rule.concern_category}' category. Concern: "
                        f"{rule.concern}. Review breastfeeding exposure, alternatives, timing, "
                        "and infant monitoring with a qualified clinician before any medication "
                        "change."
                    ),
                )
            )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.medication,
                finding.agent,
            )
        )
        logger.info("lactation_safety_checked", findings=len(findings), eligible=True)
        return findings

    @classmethod
    def _matching_rules(cls, tokens: list[str]) -> list[_LactationRule]:
        """Return lactation rules whose aliases match the medication tokens."""
        token_set = set(tokens)
        matches: list[_LactationRule] = []
        for rule in _LACTATION_RULES:
            if any(cls._alias_matches(tokens, token_set, alias) for alias in rule.aliases):
                matches.append(rule)
        return matches

    @staticmethod
    def _alias_matches(tokens: list[str], token_set: set[str], alias: tuple[str, ...]) -> bool:
        """Return True when an alias matches whole tokens or a whole token phrase."""
        if len(alias) == 1:
            return alias[0] in token_set
        if len(alias) > len(tokens):
            return False
        alias_length = len(alias)
        return any(
            tuple(tokens[index : index + alias_length]) == alias
            for index in range(len(tokens) - alias_length + 1)
        )

    @staticmethod
    def _tokens(name: str) -> list[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return re.findall(r"[a-z0-9]+", name.lower())
