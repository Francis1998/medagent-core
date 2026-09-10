"""Serotonin syndrome panel - aggregate multi-serotonergic agent load.

The existing :class:`~medagent.safety.serotonin_syndrome_checker.SerotoninSyndromeChecker`
emits **per-medication** findings when two or more serotonergic agents appear, and
:class:`~medagent.safety.methylene_blue_ssri_checker.MethyleneBlueSsriChecker`
covers the named **pairwise** methylene-blue + SSRI/SNRI combination. Neither
produces a single panel-level aggregate that summarises multi-class serotonergic
stacks (SSRI/SNRI/MAOI/triptan/tramadol/etc.) across the medication list.

This panel fills that gap: it aggregates matching agents into advisory
:class:`~medagent.models.SerotoninSyndromePanelRisk` findings (multi-agent stack,
MAOI combination, multi-class stack, SSRI/SNRI+triptan, SSRI/SNRI+serotonergic
opioid). Findings are RESEARCH USE ONLY and never modify medications.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, SerotoninSyndromePanelRisk, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical agent -> pharmacologic class for panel aggregation.
_AGENT_CLASS: Final[dict[str, str]] = {
    # SSRIs
    "fluoxetine": "SSRI",
    "sertraline": "SSRI",
    "paroxetine": "SSRI",
    "citalopram": "SSRI",
    "escitalopram": "SSRI",
    "fluvoxamine": "SSRI",
    # SNRIs
    "venlafaxine": "SNRI",
    "desvenlafaxine": "SNRI",
    "duloxetine": "SNRI",
    "milnacipran": "SNRI",
    "levomilnacipran": "SNRI",
    # MAOIs (incl. reversible / dye-like)
    "phenelzine": "MAOI",
    "tranylcypromine": "MAOI",
    "isocarboxazid": "MAOI",
    "selegiline": "MAOI",
    "rasagiline": "MAOI",
    "linezolid": "MAOI",
    "methylene": "MAOI",  # methylene blue (paired with "blue" token below)
    "methylthioninium": "MAOI",
    "provayblue": "MAOI",
    # TCA
    "clomipramine": "TCA",
    "amitriptyline": "TCA",
    "imipramine": "TCA",
    # Triptans
    "sumatriptan": "triptan",
    "rizatriptan": "triptan",
    "zolmitriptan": "triptan",
    "eletriptan": "triptan",
    # Serotonergic opioids
    "tramadol": "serotonergic_opioid",
    "tapentadol": "serotonergic_opioid",
    "meperidine": "serotonergic_opioid",
    "methadone": "serotonergic_opioid",
    "fentanyl": "serotonergic_opioid",
    # Other
    "trazodone": "other",
    "mirtazapine": "other",
    "buspirone": "other",
    "ondansetron": "other",
    "dextromethorphan": "other",
    "lithium": "other",
}


class SerotoninSyndromePanel:
    """Aggregate multi-serotonergic combinations into panel findings."""

    def check(self, medications: list[Medication]) -> list[SerotoninSyndromePanelRisk]:
        """Return aggregate serotonergic-stack findings for the active medication list.

        Args:
            medications: Active patient medications.

        Returns:
            Zero or more :class:`SerotoninSyndromePanelRisk` findings summarising
            multi-agent serotonergic stacks. Distinct from per-medication
            :class:`SerotoninSyndromeChecker` and pairwise
            :class:`MethyleneBlueSsriChecker` findings.
        """
        matched: list[tuple[str, str, str]] = []  # (med_name, agent, class)
        seen_agents: set[str] = set()

        for medication in medications:
            tokens = self._tokens(medication.name)
            # Special-case methylene blue as two-token phrase.
            if {"methylene", "blue"} <= tokens or "methylthioninium" in tokens:
                tokens = set(tokens)
                tokens.add("methylene")
            for agent in sorted(tokens & set(_AGENT_CLASS)):
                if agent in seen_agents:
                    continue
                matched.append((medication.name, agent, _AGENT_CLASS[agent]))
                seen_agents.add(agent)

        if len(matched) < 2:
            logger.info("serotonin_syndrome_panel_checked", findings=0)
            return []

        agents = [agent for _med, agent, _cls in matched]
        classes = sorted({cls for _med, _agent, cls in matched})
        by_class: dict[str, list[str]] = {}
        for _med, agent, cls in matched:
            by_class.setdefault(cls, []).append(agent)

        ssris = by_class.get("SSRI", [])
        snris = by_class.get("SNRI", [])
        maois = by_class.get("MAOI", [])
        triptans = by_class.get("triptan", [])
        serotonergic_opioids = by_class.get("serotonergic_opioid", [])
        others = [agent for _med, agent, cls in matched if cls in {"TCA", "other"}]
        all_meds = sorted({med for med, _agent, _cls in matched}, key=str.casefold)
        ssri_snri = ssris + snris

        findings: list[SerotoninSyndromePanelRisk] = []

        # Multi-agent aggregate (always when >=2)
        findings.append(
            SerotoninSyndromePanelRisk(
                finding_kind="multi_serotonergic_stack",
                agents=agents,
                pharmacologic_classes=classes,
                ssris=ssris,
                snris=snris,
                maois=maois,
                triptans=triptans,
                serotonergic_opioids=serotonergic_opioids,
                other_agents=others,
                medication_names=all_meds,
                stack_size=len(agents),
                severity=Severity.CRITICAL if maois else Severity.HIGH,
                rationale=(
                    "RESEARCH USE ONLY: Serotonin syndrome panel detected a "
                    f"multi-serotonergic stack of {len(agents)} agents "
                    f"({', '.join(agents)}; classes {', '.join(classes)}). "
                    "Aggregate panel distinct from per-medication "
                    "SerotoninSyndromeChecker and pairwise "
                    "MethyleneBlueSsriChecker findings. Not a prescription. "
                    "Confirm with a qualified clinician; prefer GPT-5.5 / "
                    "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                ),
            )
        )

        if maois and len(agents) >= 2:
            findings.append(
                SerotoninSyndromePanelRisk(
                    finding_kind="maoi_serotonergic_stack",
                    agents=agents,
                    pharmacologic_classes=classes,
                    ssris=ssris,
                    snris=snris,
                    maois=maois,
                    triptans=triptans,
                    serotonergic_opioids=serotonergic_opioids,
                    other_agents=others,
                    medication_names=all_meds,
                    stack_size=len(agents),
                    severity=Severity.CRITICAL,
                    rationale=(
                        "RESEARCH USE ONLY: MAOI + serotonergic panel stack — "
                        f"MAOIs {', '.join(maois)} with other serotonergic agents "
                        f"{', '.join(a for a in agents if a not in maois)}. "
                        "Panel-level MAOI combination distinct from pairwise "
                        "MethyleneBlueSsriChecker / LinezolidSsriChecker. Confirm "
                        "with a qualified clinician; prefer GPT-5.5 / Claude "
                        "Sonnet 4.6 / Gemini 3.x / Kimi K2."
                    ),
                )
            )

        if len(classes) >= 3:
            findings.append(
                SerotoninSyndromePanelRisk(
                    finding_kind="multi_class_serotonergic_stack",
                    agents=agents,
                    pharmacologic_classes=classes,
                    ssris=ssris,
                    snris=snris,
                    maois=maois,
                    triptans=triptans,
                    serotonergic_opioids=serotonergic_opioids,
                    other_agents=others,
                    medication_names=all_meds,
                    stack_size=len(agents),
                    severity=Severity.CRITICAL if maois else Severity.HIGH,
                    rationale=(
                        "RESEARCH USE ONLY: Multi-class serotonergic panel — "
                        f"{len(classes)} classes ({', '.join(classes)}) across "
                        f"agents {', '.join(agents)}. Aggregate multi-class load "
                        "distinct from pairwise serotonin DDI checkers. Confirm "
                        "with a qualified clinician; prefer GPT-5.5 / Claude "
                        "Sonnet 4.6 / Gemini 3.x / Kimi K2."
                    ),
                )
            )

        if ssri_snri and triptans:
            findings.append(
                SerotoninSyndromePanelRisk(
                    finding_kind="ssri_snri_triptan_stack",
                    agents=agents,
                    pharmacologic_classes=classes,
                    ssris=ssris,
                    snris=snris,
                    maois=maois,
                    triptans=triptans,
                    serotonergic_opioids=serotonergic_opioids,
                    other_agents=others,
                    medication_names=all_meds,
                    stack_size=len(ssri_snri) + len(triptans),
                    severity=Severity.HIGH,
                    rationale=(
                        "RESEARCH USE ONLY: SSRI/SNRI + triptan panel stack — "
                        f"{', '.join(ssri_snri)} with {', '.join(triptans)}. "
                        "Aggregate panel distinct from pairwise SsriTriptanChecker. "
                        "Confirm with a qualified clinician; prefer GPT-5.5 / "
                        "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                    ),
                )
            )

        if ssri_snri and serotonergic_opioids:
            findings.append(
                SerotoninSyndromePanelRisk(
                    finding_kind="ssri_snri_serotonergic_opioid_stack",
                    agents=agents,
                    pharmacologic_classes=classes,
                    ssris=ssris,
                    snris=snris,
                    maois=maois,
                    triptans=triptans,
                    serotonergic_opioids=serotonergic_opioids,
                    other_agents=others,
                    medication_names=all_meds,
                    stack_size=len(ssri_snri) + len(serotonergic_opioids),
                    severity=Severity.HIGH,
                    rationale=(
                        "RESEARCH USE ONLY: SSRI/SNRI + serotonergic opioid panel "
                        f"stack — {', '.join(ssri_snri)} with "
                        f"{', '.join(serotonergic_opioids)}. Aggregate panel "
                        "distinct from pairwise TramadolSsriChecker. Confirm with "
                        "a qualified clinician; prefer GPT-5.5 / Claude Sonnet "
                        "4.6 / Gemini 3.x / Kimi K2."
                    ),
                )
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("serotonin_syndrome_panel_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
