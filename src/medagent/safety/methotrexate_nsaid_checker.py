"""Methotrexate + NSAID reduced-clearance toxicity safety checker.

NSAIDs can reduce renal methotrexate clearance and increase methotrexate
toxicity risk. This brand-aware methotrexate × NSAID control is distinct from
the legacy `mtx_nsaid_checker`, methotrexate + TMP-SMX, and other NSAID
bleed-risk checkers.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, MethotrexateNsaidRisk, Severity

logger = get_logger(__name__)

_PRIMARY_AGENTS: Final[dict[str, str]] = {
    "methotrexate": "an antifolate with dose- and clearance-dependent toxicity",
    "trexall": "a methotrexate brand antifolate",
    "otrexup": "a methotrexate brand autofill injector",
    "rasuvo": "a methotrexate brand subcutaneous injector",
    "xatmep": "a methotrexate brand oral solution",
}

_PARTNER_AGENTS: Final[dict[str, tuple[str, Severity]]] = {
    "ibuprofen": (
        "an NSAID that can reduce renal methotrexate clearance",
        Severity.HIGH,
    ),
    "naproxen": (
        "an NSAID that can reduce renal methotrexate clearance",
        Severity.HIGH,
    ),
    "diclofenac": (
        "an NSAID that can reduce renal methotrexate clearance",
        Severity.HIGH,
    ),
    "ketorolac": (
        "a potent NSAID that can markedly reduce methotrexate clearance",
        Severity.CRITICAL,
    ),
    "indomethacin": (
        "an NSAID associated with reduced methotrexate clearance",
        Severity.HIGH,
    ),
    "meloxicam": (
        "an NSAID that can reduce renal methotrexate clearance",
        Severity.HIGH,
    ),
    "celecoxib": (
        "a COX-2-selective NSAID that can reduce methotrexate clearance",
        Severity.HIGH,
    ),
    "nsaid": (
        "a nonsteroidal anti-inflammatory drug that can reduce methotrexate clearance",
        Severity.HIGH,
    ),
}

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


class MethotrexateNsaidChecker:
    """Flag methotrexate co-prescribed with supported NSAIDs."""

    def check(self, medications: list[Medication]) -> list[MethotrexateNsaidRisk]:
        """Return one finding per unique methotrexate × NSAID pair."""
        primary_matches: list[tuple[int, Medication, str]] = []
        partner_matches: list[tuple[int, Medication, str]] = []

        for index, medication in enumerate(medications):
            primary_agent = self._match_agent(medication.name, _PRIMARY_AGENTS)
            if primary_agent is not None:
                primary_matches.append((index, medication, primary_agent))

            partner_agent = self._match_agent(medication.name, _PARTNER_AGENTS)
            if partner_agent is not None:
                partner_matches.append((index, medication, partner_agent))

        if not primary_matches or not partner_matches:
            logger.info("methotrexate_nsaid_checked", findings=0)
            return []

        primary_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        partner_matches.sort(key=lambda match: (match[1].name.lower(), match[2], match[0]))
        findings: list[MethotrexateNsaidRisk] = []
        seen: set[tuple[str, str]] = set()

        for primary_index, primary_med, primary_agent in primary_matches:
            for partner_index, partner_med, partner_agent in partner_matches:
                pair_key = (primary_agent, partner_agent)
                if primary_index == partner_index or pair_key in seen:
                    continue
                seen.add(pair_key)
                _partner_descriptor, severity = _PARTNER_AGENTS[partner_agent]
                findings.append(
                    MethotrexateNsaidRisk(
                        medication=primary_med.name,
                        agent=primary_agent,
                        partner_medication=partner_med.name,
                        partner_agent=partner_agent,
                        severity=severity,
                        rationale=self._build_rationale(
                            primary_medication=primary_med.name,
                            primary_agent=primary_agent,
                            partner_medication=partner_med.name,
                            partner_agent=partner_agent,
                        ),
                    )
                )

        findings.sort(
            key=lambda finding: (
                -_SEVERITY_RANK[finding.severity],
                finding.medication.lower(),
                finding.partner_medication.lower(),
                finding.agent,
                finding.partner_agent,
            )
        )
        logger.info("methotrexate_nsaid_checked", findings=len(findings))
        return findings

    @staticmethod
    def _build_rationale(
        *,
        primary_medication: str,
        primary_agent: str,
        partner_medication: str,
        partner_agent: str,
    ) -> str:
        partner_descriptor, _severity = _PARTNER_AGENTS[partner_agent]
        return (
            "RESEARCH USE ONLY: "
            f"Medication '{primary_medication}' contains {primary_agent}, "
            f"{_PRIMARY_AGENTS[primary_agent]}, and is co-prescribed with "
            f"'{partner_medication}' ({partner_agent}, {partner_descriptor}). "
            "NSAIDs can reduce methotrexate clearance and increase toxicity "
            "risk (myelosuppression, mucositis, renal injury, hepatotoxicity). "
            "Obtain urgent qualified clinical and pharmacist review; do not "
            "change therapy from this research output."
        )

    @staticmethod
    def _match_agent(
        name: str, agents: dict[str, str] | dict[str, tuple[str, Severity]]
    ) -> str | None:
        """Return the most specific whole-token/whole-alias match in ``name``."""
        lowered = name.lower()
        aliases = sorted(agents, key=lambda alias: (-len(alias.split()), -len(alias), alias))
        for alias in aliases:
            components = [re.escape(component) for component in alias.replace("-", " ").split()]
            pattern = r"(?<![a-z0-9])" + r"[\s_-]+".join(components) + r"(?![a-z0-9])"
            if re.search(pattern, lowered):
                return alias
        return None
