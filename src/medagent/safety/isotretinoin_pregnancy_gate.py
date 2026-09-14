"""Isotretinoin absolute pregnancy contraindication gate.

The existing :class:`~medagent.safety.pregnancy_checker.PregnancySafetyChecker`
flags many teratogens when ``pregnant=True``, and
:class:`~medagent.safety.isotretinoin_tetracycline_checker.IsotretinoinTetracyclineChecker`
covers isotretinoin + tetracycline intracranial-hypertension DDIs — neither is an
isotretinoin-specific absolute pregnancy / iPLEDGE-style gate.

This gate fills that gap: it maps isotretinoin exposure plus pregnancy or
pregnancy-capable context into advisory
:class:`~medagent.models.IsotretinoinPregnancyGateAlert` findings.
RESEARCH USE ONLY; never modifies medications.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import IsotretinoinPregnancyGateAlert, Medication, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_ISOTRETINOIN_AGENTS: Final[frozenset[str]] = frozenset(
    {
        "isotretinoin",
        "accutane",
        "absorica",
        "claravis",
        "myorisan",
        "zenatane",
    }
)


class IsotretinoinPregnancyGate:
    """Absolute pregnancy contraindication / prevention gate for isotretinoin."""

    def check(
        self,
        medications: list[Medication],
        *,
        pregnant: bool = False,
        pregnancy_capable: bool = False,
    ) -> list[IsotretinoinPregnancyGateAlert]:
        """Return isotretinoin pregnancy-gate advisories.

        Args:
            medications: Active medications.
            pregnant: True when pregnancy is documented.
            pregnancy_capable: True when pregnancy-capable context is documented
                (iPLEDGE-style prevention cue without confirmed pregnancy).

        Returns:
            Zero or more :class:`IsotretinoinPregnancyGateAlert` findings.
            Distinct from :class:`PregnancySafetyChecker` and
            :class:`IsotretinoinTetracyclineChecker`. Never modifies medications.
        """
        matched: list[tuple[str, str]] = []
        seen: set[str] = set()
        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _ISOTRETINOIN_AGENTS):
                if agent in seen:
                    continue
                matched.append((medication.name, agent))
                seen.add(agent)

        agents = [agent for _med, agent in matched]
        med_names = sorted({med for med, _agent in matched}, key=str.casefold)

        if not agents or (not pregnant and not pregnancy_capable):
            logger.info("isotretinoin_pregnancy_gate_checked", findings=0)
            return []

        findings: list[IsotretinoinPregnancyGateAlert] = []

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                IsotretinoinPregnancyGateAlert(
                    finding_kind=kind,
                    agents=agents,
                    medication_names=med_names,
                    pregnant=pregnant,
                    pregnancy_capable=pregnancy_capable,
                    severity=severity,
                    rationale=rationale,
                )
            )

        if pregnant:
            _add(
                "isotretinoin_absolute_pregnancy_contraindication",
                Severity.CRITICAL,
                (
                    "RESEARCH USE ONLY: Absolute pregnancy contraindication for "
                    f"isotretinoin ({', '.join(agents)}). Documented pregnancy "
                    "with isotretinoin exposure is a CRITICAL teratogen gate "
                    "distinct from generic PregnancySafetyChecker multi-agent "
                    "screening and IsotretinoinTetracyclineChecker DDI checks. "
                    "Never modifies medications. Confirm with a qualified "
                    "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x "
                    "/ Kimi K2."
                ),
            )

        if pregnancy_capable and not pregnant:
            _add(
                "isotretinoin_pregnancy_prevention_required",
                Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Isotretinoin pregnancy-prevention gate "
                    f"for agents {', '.join(agents)} in pregnancy-capable "
                    "context (iPLEDGE-style advisory). Distinct from generic "
                    "PregnancySafetyChecker and IsotretinoinTetracyclineChecker. "
                    "Never modifies medications. Confirm with a qualified "
                    "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x "
                    "/ Kimi K2."
                ),
            )

        if pregnant or pregnancy_capable:
            _add(
                "isotretinoin_teratogen_gate",
                Severity.CRITICAL if pregnant else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Isotretinoin teratogen gate advisory for "
                    f"agents {', '.join(agents)} "
                    f"(pregnant={pregnant}, pregnancy_capable={pregnancy_capable}). "
                    "Absolute pregnancy contraindication control distinct from "
                    "PregnancySafetyChecker and IsotretinoinTetracyclineChecker. "
                    "Never modifies medications. Confirm with a qualified "
                    "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x "
                    "/ Kimi K2."
                ),
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("isotretinoin_pregnancy_gate_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
