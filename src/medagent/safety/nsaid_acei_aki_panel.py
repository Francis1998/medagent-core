"""NSAID + ACEI/ARB AKI/bleeding advisory panel.

The existing :class:`~medagent.safety.triple_whammy_checker.TripleWhammyChecker`
requires concurrent **NSAID + ACEI/ARB/ARNI + loop/thiazide diuretic** and emits
per-triad :class:`~medagent.models.TripleWhammyRisk` findings. It does **not**
fire on the dual NSAID+ACEI/ARB pair alone.

This panel fills that gap: it aggregates NSAID + ACEI/ARB into advisory
:class:`~medagent.models.NsaidAceiAkiPanelRisk` findings even without a
diuretic, and escalates severity when a diuretic is also present (triple-whammy
awareness). Findings are RESEARCH USE ONLY and never modify medications.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, NsaidAceiAkiPanelRisk, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

_NSAID_AGENTS: Final[frozenset[str]] = frozenset(
    {
        "ibuprofen",
        "naproxen",
        "diclofenac",
        "ketorolac",
        "meloxicam",
        "celecoxib",
        "indomethacin",
    }
)

_ACEI_ARB_AGENTS: Final[frozenset[str]] = frozenset(
    {
        "lisinopril",
        "enalapril",
        "ramipril",
        "benazepril",
        "captopril",
        "losartan",
        "valsartan",
        "olmesartan",
        "irbesartan",
        "candesartan",
        "sacubitril",
    }
)

_DIURETIC_AGENTS: Final[frozenset[str]] = frozenset(
    {
        "furosemide",
        "bumetanide",
        "torsemide",
        "hctz",
        "hydrochlorothiazide",
        "chlorthalidone",
        "metolazone",
    }
)


class NsaidAceiAkiPanel:
    """Aggregate NSAID + ACEI/ARB AKI/bleeding panel findings."""

    def check(self, medications: list[Medication]) -> list[NsaidAceiAkiPanelRisk]:
        """Return NSAID+ACEI/ARB AKI/bleeding panel findings.

        Args:
            medications: Active patient medications.

        Returns:
            Zero or more :class:`NsaidAceiAkiPanelRisk` findings. Distinct from
            triad-requiring :class:`TripleWhammyChecker`. Never modifies
            medications.
        """
        nsaids: list[tuple[str, str]] = []
        aceis: list[tuple[str, str]] = []
        diuretics: list[tuple[str, str]] = []
        seen_n: set[str] = set()
        seen_a: set[str] = set()
        seen_d: set[str] = set()

        for medication in medications:
            tokens = self._tokens(medication.name)
            for agent in sorted(tokens & _NSAID_AGENTS):
                if agent in seen_n:
                    continue
                nsaids.append((medication.name, agent))
                seen_n.add(agent)
            for agent in sorted(tokens & _ACEI_ARB_AGENTS):
                if agent in seen_a:
                    continue
                aceis.append((medication.name, agent))
                seen_a.add(agent)
            for agent in sorted(tokens & _DIURETIC_AGENTS):
                if agent in seen_d:
                    continue
                diuretics.append((medication.name, agent))
                seen_d.add(agent)

        nsaid_agents = [agent for _med, agent in nsaids]
        acei_agents = [agent for _med, agent in aceis]
        diuretic_agents = [agent for _med, agent in diuretics]
        all_meds = sorted(
            {med for med, _agent in nsaids + aceis + diuretics},
            key=str.casefold,
        )

        if not nsaid_agents or not acei_agents:
            logger.info("nsaid_acei_aki_panel_checked", findings=0)
            return []

        findings: list[NsaidAceiAkiPanelRisk] = []
        has_diuretic = bool(diuretic_agents)

        def _add(kind: str, severity: Severity, rationale: str) -> None:
            findings.append(
                NsaidAceiAkiPanelRisk(
                    finding_kind=kind,
                    nsaids=nsaid_agents,
                    acei_arb_agents=acei_agents,
                    diuretics=diuretic_agents,
                    medication_names=all_meds,
                    severity=severity,
                    rationale=rationale,
                )
            )

        dual_sev = Severity.CRITICAL if has_diuretic else Severity.HIGH
        _add(
            "nsaid_acei_dual_aki_panel",
            dual_sev,
            (
                "RESEARCH USE ONLY: NSAID + ACEI/ARB AKI/bleeding panel — NSAIDs "
                f"({', '.join(nsaid_agents)}) with ACEI/ARB/ARNI "
                f"({', '.join(acei_agents)}). Dual-pair aggregate fires even "
                "without a diuretic; distinct from triad-requiring "
                "TripleWhammyChecker. Never modifies medications. Confirm with "
                "a qualified clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / "
                "Gemini 3.x / Kimi K2."
            ),
        )

        if has_diuretic:
            _add(
                "nsaid_acei_diuretic_escalation",
                Severity.CRITICAL,
                (
                    "RESEARCH USE ONLY: NSAID + ACEI/ARB panel escalation — "
                    f"diuretic(s) {', '.join(diuretic_agents)} also present "
                    f"with NSAIDs ({', '.join(nsaid_agents)}) and ACEI/ARB "
                    f"({', '.join(acei_agents)}). Triple-whammy awareness "
                    "escalation in panel framing; distinct from per-triad "
                    "TripleWhammyChecker findings. Never modifies medications. "
                    "Confirm with a qualified clinician; prefer GPT-5.5 / "
                    "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        if len(nsaid_agents) >= 2:
            _add(
                "multi_nsaid_on_acei_arb",
                Severity.CRITICAL if has_diuretic else Severity.HIGH,
                (
                    "RESEARCH USE ONLY: Multiple NSAIDs on ACEI/ARB therapy — "
                    f"{', '.join(nsaid_agents)} with {', '.join(acei_agents)}. "
                    "Panel-level multi-NSAID AKI/bleeding aggregate distinct "
                    "from TripleWhammyChecker. Never modifies medications. "
                    "Confirm with a qualified clinician; prefer GPT-5.5 / "
                    "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info(
            "nsaid_acei_aki_panel_checked",
            findings=len(findings),
            nsaids=len(nsaid_agents),
            acei_arb=len(acei_agents),
            diuretics=len(diuretic_agents),
        )
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
