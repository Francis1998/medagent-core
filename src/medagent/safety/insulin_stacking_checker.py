"""Insulin stacking safety checker.

Overlapping rapid-acting insulin boluses within a short interval, or concurrent
premix and bolus insulin regimens, increase the risk of hypoglycemia from
cumulative insulin effect. This hazard is distinct from generic medication
interaction screening.

This checker flags rapid-acting insulin when `hours_since_last_bolus` is below
three hours without meal or correction context, and flags concurrent premix plus
bolus insulin combinations. Whole-token matching is used throughout. Findings
are deterministic and RESEARCH USE ONLY.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import InsulinStackingRisk, Medication, Severity

logger = get_logger(__name__)

_BOLUS_STACKING_HOURS_THRESHOLD: Final[float] = 3.0

# Higher rank = more severe, used to order findings deterministically.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_FINDING_KIND_RANK: Final[dict[str, int]] = {
    "rapid_bolus_stacking": 0,
    "premix_plus_bolus": 1,
}

# Canonical rapid-acting insulin token -> short descriptor.
_RAPID_INSULIN_AGENTS: Final[dict[str, str]] = {
    "lispro": "a rapid-acting insulin analog",
    "aspart": "a rapid-acting insulin analog",
    "glulisine": "a rapid-acting insulin analog",
}

# Canonical premix insulin token -> short descriptor.
_PREMIX_TOKEN_AGENTS: Final[dict[str, str]] = {
    "protamine": "a premix insulin component (protamine suspension)",
    "mix": "a premix insulin formulation",
}

_PREMIX_RATIO_TOKEN_PAIRS: Final[tuple[tuple[frozenset[str], str], ...]] = (
    (frozenset({"70", "30"}), "70/30"),
    (frozenset({"75", "25"}), "75/25"),
)


class InsulinStackingChecker:
    """Flag overlapping rapid-acting insulin boluses and premix plus bolus combinations."""

    def check(
        self,
        medications: list[Medication],
        hours_since_last_bolus: float | None = None,
        meal_context: bool = False,
        correction_context: bool = False,
    ) -> list[InsulinStackingRisk]:
        """Return findings for insulin stacking hazards.

        Args:
            medications: Active patient medications.
            hours_since_last_bolus: Hours since the most recent rapid-acting bolus,
                or None when unknown.
            meal_context: True when a meal bolus context is documented.
            correction_context: True when a correction bolus context is documented.

        Returns:
            One :class:`InsulinStackingRisk` per applicable finding, ordered by
            descending severity then medication name and finding kind.
        """
        rapid_matches: list[tuple[Medication, str]] = []
        premix_matches: list[tuple[Medication, str]] = []

        for medication in medications:
            tokens = self._tokens(medication.name)
            if not tokens:
                continue

            rapid_candidates = sorted(tokens & set(_RAPID_INSULIN_AGENTS))
            if rapid_candidates:
                rapid_matches.append((medication, rapid_candidates[0]))

            premix_candidate = self._premix_agent(tokens)
            if premix_candidate is not None:
                premix_matches.append((medication, premix_candidate))

        if not rapid_matches and not premix_matches:
            logger.info("insulin_stacking_checked", findings=0)
            return []

        findings: list[InsulinStackingRisk] = []
        has_context = meal_context or correction_context

        if (
            rapid_matches
            and hours_since_last_bolus is not None
            and hours_since_last_bolus < _BOLUS_STACKING_HOURS_THRESHOLD
            and not has_context
        ):
            for medication, agent in rapid_matches:
                findings.append(
                    self._build_finding(
                        medication_name=medication.name,
                        agent=agent,
                        finding_kind="rapid_bolus_stacking",
                        hours_since_last_bolus=hours_since_last_bolus,
                        meal_context=meal_context,
                        correction_context=correction_context,
                        partner_medication=None,
                        partner_agent=None,
                    )
                )

        if rapid_matches and premix_matches:
            for premix_med, premix_agent in premix_matches:
                for rapid_med, rapid_agent in rapid_matches:
                    findings.append(
                        self._build_finding(
                            medication_name=premix_med.name,
                            agent=premix_agent,
                            finding_kind="premix_plus_bolus",
                            hours_since_last_bolus=hours_since_last_bolus,
                            meal_context=meal_context,
                            correction_context=correction_context,
                            partner_medication=rapid_med.name,
                            partner_agent=rapid_agent,
                        )
                    )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.medication.lower(),
                _FINDING_KIND_RANK[finding.finding_kind],
                finding.agent,
                (finding.partner_medication or "").lower(),
            )
        )
        logger.info(
            "insulin_stacking_checked",
            findings=len(findings),
            rapid_agents=len({agent for _med, agent in rapid_matches}),
            premix_agents=len({agent for _med, agent in premix_matches}),
        )
        return findings

    def _build_finding(
        self,
        *,
        medication_name: str,
        agent: str,
        finding_kind: str,
        hours_since_last_bolus: float | None,
        meal_context: bool,
        correction_context: bool,
        partner_medication: str | None,
        partner_agent: str | None,
    ) -> InsulinStackingRisk:
        """Construct a single insulin stacking finding."""
        if finding_kind == "rapid_bolus_stacking":
            descriptor = _RAPID_INSULIN_AGENTS[agent]
        elif agent in _PREMIX_TOKEN_AGENTS:
            descriptor = _PREMIX_TOKEN_AGENTS[agent]
        else:
            descriptor = f"a {agent} premix insulin formulation"

        return InsulinStackingRisk(
            medication=medication_name,
            agent=agent,
            finding_kind=finding_kind,
            partner_medication=partner_medication,
            partner_agent=partner_agent,
            hours_since_last_bolus=hours_since_last_bolus,
            meal_context=meal_context,
            correction_context=correction_context,
            severity=self._severity_for_kind(finding_kind),
            rationale=self._build_rationale(
                medication_name=medication_name,
                agent=agent,
                descriptor=descriptor,
                finding_kind=finding_kind,
                hours_since_last_bolus=hours_since_last_bolus,
                meal_context=meal_context,
                correction_context=correction_context,
                partner_medication=partner_medication,
                partner_agent=partner_agent,
            ),
        )

    @staticmethod
    def _severity_for_kind(finding_kind: str) -> Severity:
        """Map finding kind to advisory severity."""
        if finding_kind == "premix_plus_bolus":
            return Severity.CRITICAL
        return Severity.HIGH

    @staticmethod
    def _build_rationale(
        *,
        medication_name: str,
        agent: str,
        descriptor: str,
        finding_kind: str,
        hours_since_last_bolus: float | None,
        meal_context: bool,
        correction_context: bool,
        partner_medication: str | None,
        partner_agent: str | None,
    ) -> str:
        """Compose a RESEARCH USE ONLY insulin stacking rationale."""
        if finding_kind == "rapid_bolus_stacking":
            detail = (
                f"rapid-acting insulin bolus was given {hours_since_last_bolus:.1f} hours ago "
                f"(threshold < {_BOLUS_STACKING_HOURS_THRESHOLD:.0f} hours) without documented "
                "meal or correction context"
            )
        else:
            detail = (
                f"premix insulin '{medication_name}' ({agent}) is co-prescribed with bolus "
                f"insulin '{partner_medication}' ({partner_agent}), creating overlapping "
                "rapid-acting insulin exposure"
            )

        return (
            "RESEARCH USE ONLY: "
            f"Medication '{medication_name}' contains {agent}, {descriptor}. "
            f"Insulin stacking risk is elevated because {detail}. "
            "Overlapping rapid-acting insulin doses increase hypoglycemia risk. "
            "Review insulin regimen, timing, and glucose monitoring urgently."
        )

    @staticmethod
    def _premix_agent(tokens: set[str]) -> str | None:
        """Return a canonical premix agent token when premix markers are present."""
        token_hits = sorted(tokens & set(_PREMIX_TOKEN_AGENTS))
        if token_hits:
            return token_hits[0]
        for ratio_tokens, ratio_label in _PREMIX_RATIO_TOKEN_PAIRS:
            if ratio_tokens.issubset(tokens):
                return ratio_label
        return None

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric component tokens of a medication name."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
