"""Pregnancy/lactation risk panel - aggregate reproductive-risk summary.

The existing :class:`~medagent.safety.pregnancy_lactation_checker.PregnancyLactationChecker`
emits **per-medication** pregnancy / lactation / combined findings. It does not
produce a single panel-level aggregate that summarises how many pregnancy vs
lactation hits (and dual hits) appear across the full medication list, with
optional trimester context.

This panel fills that gap: it aggregates matching reproductive-risk agents into
advisory :class:`~medagent.models.PregnancyLactationPanelRisk` findings
(panel summary, pregnancy aggregate, lactation aggregate, dual-hit aggregate,
optional trimester context). Findings are RESEARCH USE ONLY and never modify
medications.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, PregnancyLactationPanelRisk, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical pregnancy-panel agent -> (baseline severity, short reason)
_PREGNANCY_PANEL: Final[dict[str, tuple[Severity, str]]] = {
    "isotretinoin": (Severity.CRITICAL, "potent teratogen"),
    "thalidomide": (Severity.CRITICAL, "potent teratogen"),
    "methotrexate": (Severity.CRITICAL, "abortifacient teratogen"),
    "misoprostol": (Severity.CRITICAL, "abortifacient"),
    "warfarin": (Severity.HIGH, "fetal warfarin syndrome"),
    "valproate": (Severity.HIGH, "neural-tube / neurodevelopmental risk"),
    "valproic": (Severity.HIGH, "neural-tube risk"),
    "phenytoin": (Severity.HIGH, "fetal hydantoin syndrome"),
    "carbamazepine": (Severity.HIGH, "neural-tube risk"),
    "lithium": (Severity.HIGH, "cardiac anomaly risk"),
    "methimazole": (Severity.HIGH, "aplasia cutis / choanal atresia risk"),
    "lisinopril": (Severity.HIGH, "ACE inhibitor fetal renopathy"),
    "enalapril": (Severity.HIGH, "ACE inhibitor fetal renopathy"),
    "ramipril": (Severity.HIGH, "ACE inhibitor fetal renopathy"),
    "captopril": (Severity.HIGH, "ACE inhibitor fetal renopathy"),
    "losartan": (Severity.HIGH, "ARB fetal renopathy"),
    "valsartan": (Severity.HIGH, "ARB fetal renopathy"),
    "irbesartan": (Severity.HIGH, "ARB fetal renopathy"),
    "tetracycline": (Severity.MODERATE, "dental staining / bone-growth effects"),
    "doxycycline": (Severity.MODERATE, "dental staining / bone-growth effects"),
    "minocycline": (Severity.MODERATE, "dental staining / bone-growth effects"),
}

# Canonical lactation-panel agent -> (baseline severity, short reason)
_LACTATION_PANEL: Final[dict[str, tuple[Severity, str]]] = {
    "radioiodine": (Severity.CRITICAL, "infant thyroid radiation exposure"),
    "cyclophosphamide": (Severity.CRITICAL, "antineoplastic milk transfer"),
    "doxorubicin": (Severity.CRITICAL, "antineoplastic milk transfer"),
    "methotrexate": (Severity.CRITICAL, "antimetabolite milk transfer"),
    "fluorouracil": (Severity.CRITICAL, "antimetabolite milk transfer"),
    "capecitabine": (Severity.CRITICAL, "antimetabolite milk transfer"),
    "amiodarone": (Severity.HIGH, "infant thyroid / cardiac exposure"),
    "lithium": (Severity.HIGH, "infant serum accumulation"),
    "codeine": (Severity.HIGH, "opioid infant sedation risk"),
    "tramadol": (Severity.HIGH, "opioid infant sedation risk"),
}

# Agents whose pregnancy hazard is amplified in 2nd/3rd trimester.
_TRIMESTER_SENSITIVE: Final[frozenset[str]] = frozenset(
    {
        "lisinopril",
        "enalapril",
        "ramipril",
        "captopril",
        "losartan",
        "valsartan",
        "irbesartan",
        "tetracycline",
        "doxycycline",
        "minocycline",
    }
)

_TRIMESTER_ALIASES: Final[dict[str, str]] = {
    "1": "1",
    "first": "1",
    "t1": "1",
    "2": "2",
    "second": "2",
    "t2": "2",
    "3": "3",
    "third": "3",
    "t3": "3",
}


class PregnancyLactationRiskPanel:
    """Aggregate pregnancy/lactation hits into panel-level advisory findings."""

    def check(
        self,
        medications: list[Medication],
        *,
        pregnant: bool = True,
        breastfeeding: bool = True,
        trimester: str | None = None,
    ) -> list[PregnancyLactationPanelRisk]:
        """Return aggregate reproductive-risk panel findings for a medication list.

        Args:
            medications: Active patient medications.
            pregnant: When False, pregnancy-panel agents are ignored.
            breastfeeding: When False, lactation-panel agents are ignored.
            trimester: Optional trimester context (``1``/``2``/``3`` or aliases).

        Returns:
            Zero or more :class:`PregnancyLactationPanelRisk` findings summarising
            pregnancy vs lactation hit counts, dual hits, and optional trimester
            context. Distinct from per-medication
            :class:`PregnancyLactationChecker` findings.
        """
        if not pregnant and not breastfeeding:
            logger.info("pregnancy_lactation_risk_panel_checked", findings=0, eligible=False)
            return []

        pregnancy_matched: list[tuple[str, str, Severity]] = []
        lactation_matched: list[tuple[str, str, Severity]] = []
        seen_pregnancy: set[str] = set()
        seen_lactation: set[str] = set()
        med_by_agent: dict[str, str] = {}

        for medication in medications:
            tokens = self._tokens(medication.name)
            if pregnant:
                for agent in sorted(tokens & set(_PREGNANCY_PANEL)):
                    if agent in seen_pregnancy:
                        continue
                    severity, _reason = _PREGNANCY_PANEL[agent]
                    pregnancy_matched.append((medication.name, agent, severity))
                    seen_pregnancy.add(agent)
                    med_by_agent.setdefault(agent, medication.name)
            if breastfeeding:
                # Special-case radioiodine phrase tokens.
                lact_tokens = set(tokens)
                if {"i", "131"} <= lact_tokens or {"radioactive", "iodine"} <= lact_tokens:
                    lact_tokens.add("radioiodine")
                for agent in sorted(lact_tokens & set(_LACTATION_PANEL)):
                    if agent in seen_lactation:
                        continue
                    severity, _reason = _LACTATION_PANEL[agent]
                    lactation_matched.append((medication.name, agent, severity))
                    seen_lactation.add(agent)
                    med_by_agent.setdefault(agent, medication.name)

        pregnancy_agents = [agent for _med, agent, _sev in pregnancy_matched]
        lactation_agents = [agent for _med, agent, _sev in lactation_matched]
        dual_hit_agents = sorted(set(pregnancy_agents) & set(lactation_agents))
        all_meds = sorted(
            {med for med, _agent, _sev in pregnancy_matched + lactation_matched},
            key=str.casefold,
        )

        if not pregnancy_agents and not lactation_agents:
            logger.info("pregnancy_lactation_risk_panel_checked", findings=0)
            return []

        normalized_trimester = self._normalize_trimester(trimester)
        findings: list[PregnancyLactationPanelRisk] = []

        max_sev = Severity.LOW
        for _med, _agent, sev in pregnancy_matched + lactation_matched:
            if _SEVERITY_RANK[sev] > _SEVERITY_RANK[max_sev]:
                max_sev = sev
        if dual_hit_agents and _SEVERITY_RANK[max_sev] < _SEVERITY_RANK[Severity.HIGH]:
            max_sev = Severity.HIGH
        if len(pregnancy_agents) + len(lactation_agents) >= 3:
            if _SEVERITY_RANK[max_sev] < _SEVERITY_RANK[Severity.HIGH]:
                max_sev = Severity.HIGH
        if dual_hit_agents and any(
            _PREGNANCY_PANEL.get(a, (Severity.LOW, ""))[0] is Severity.CRITICAL
            or _LACTATION_PANEL.get(a, (Severity.LOW, ""))[0] is Severity.CRITICAL
            for a in dual_hit_agents
        ):
            max_sev = Severity.CRITICAL

        findings.append(
            PregnancyLactationPanelRisk(
                finding_kind="panel_summary",
                pregnancy_hit_count=len(pregnancy_agents),
                lactation_hit_count=len(lactation_agents),
                dual_hit_count=len(dual_hit_agents),
                pregnancy_agents=pregnancy_agents,
                lactation_agents=lactation_agents,
                dual_hit_agents=dual_hit_agents,
                medication_names=all_meds,
                trimester=normalized_trimester,
                severity=max_sev,
                rationale=(
                    "RESEARCH USE ONLY: Pregnancy/lactation risk panel summary — "
                    f"{len(pregnancy_agents)} pregnancy hit(s), "
                    f"{len(lactation_agents)} lactation hit(s), "
                    f"{len(dual_hit_agents)} dual hit(s) across medications "
                    f"{', '.join(all_meds) or 'n/a'}. Aggregate panel distinct from "
                    "per-medication PregnancyLactationChecker findings. Not a "
                    "prescription. Confirm with a qualified clinician; prefer "
                    "frontier summarization with GPT-5.5 / Claude Sonnet 4.6 / "
                    "Gemini 3.x / Kimi K2."
                ),
            )
        )

        if len(pregnancy_agents) >= 2:
            findings.append(
                PregnancyLactationPanelRisk(
                    finding_kind="pregnancy_aggregate",
                    pregnancy_hit_count=len(pregnancy_agents),
                    lactation_hit_count=len(lactation_agents),
                    dual_hit_count=len(dual_hit_agents),
                    pregnancy_agents=pregnancy_agents,
                    lactation_agents=lactation_agents,
                    dual_hit_agents=dual_hit_agents,
                    medication_names=[
                        med for med, agent, _sev in pregnancy_matched if agent in pregnancy_agents
                    ],
                    trimester=normalized_trimester,
                    severity=Severity.HIGH
                    if len(pregnancy_agents) >= 3
                    else Severity.MODERATE,
                    rationale=(
                        "RESEARCH USE ONLY: Pregnancy aggregate panel detected "
                        f"{len(pregnancy_agents)} distinct pregnancy-risk agents "
                        f"({', '.join(pregnancy_agents)}). Distinct from "
                        "PregnancyLactationChecker per-med findings. Confirm with "
                        "a qualified clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / "
                        "Gemini 3.x / Kimi K2."
                    ),
                )
            )

        if len(lactation_agents) >= 2:
            findings.append(
                PregnancyLactationPanelRisk(
                    finding_kind="lactation_aggregate",
                    pregnancy_hit_count=len(pregnancy_agents),
                    lactation_hit_count=len(lactation_agents),
                    dual_hit_count=len(dual_hit_agents),
                    pregnancy_agents=pregnancy_agents,
                    lactation_agents=lactation_agents,
                    dual_hit_agents=dual_hit_agents,
                    medication_names=[
                        med for med, agent, _sev in lactation_matched if agent in lactation_agents
                    ],
                    trimester=normalized_trimester,
                    severity=Severity.HIGH
                    if len(lactation_agents) >= 3
                    else Severity.MODERATE,
                    rationale=(
                        "RESEARCH USE ONLY: Lactation aggregate panel detected "
                        f"{len(lactation_agents)} distinct lactation-risk agents "
                        f"({', '.join(lactation_agents)}). Distinct from "
                        "PregnancyLactationChecker per-med findings. Confirm with "
                        "a qualified clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / "
                        "Gemini 3.x / Kimi K2."
                    ),
                )
            )

        if dual_hit_agents:
            dual_sev = Severity.HIGH
            if any(
                _PREGNANCY_PANEL.get(a, (Severity.LOW, ""))[0] is Severity.CRITICAL
                or _LACTATION_PANEL.get(a, (Severity.LOW, ""))[0] is Severity.CRITICAL
                for a in dual_hit_agents
            ):
                dual_sev = Severity.CRITICAL
            findings.append(
                PregnancyLactationPanelRisk(
                    finding_kind="dual_hit_aggregate",
                    pregnancy_hit_count=len(pregnancy_agents),
                    lactation_hit_count=len(lactation_agents),
                    dual_hit_count=len(dual_hit_agents),
                    pregnancy_agents=pregnancy_agents,
                    lactation_agents=lactation_agents,
                    dual_hit_agents=dual_hit_agents,
                    medication_names=[
                        med_by_agent[a] for a in dual_hit_agents if a in med_by_agent
                    ],
                    trimester=normalized_trimester,
                    severity=dual_sev,
                    rationale=(
                        "RESEARCH USE ONLY: Dual-hit reproductive panel — agents "
                        f"{', '.join(dual_hit_agents)} appear on both pregnancy and "
                        "lactation curated panels. Aggregate dual-hit count "
                        f"{len(dual_hit_agents)} is distinct from per-medication "
                        "PregnancyLactationChecker combined findings. Confirm with "
                        "a qualified clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / "
                        "Gemini 3.x / Kimi K2."
                    ),
                )
            )

        if normalized_trimester in {"2", "3"} and pregnancy_agents:
            sensitive = sorted(set(pregnancy_agents) & _TRIMESTER_SENSITIVE)
            if sensitive:
                findings.append(
                    PregnancyLactationPanelRisk(
                        finding_kind="trimester_context",
                        pregnancy_hit_count=len(pregnancy_agents),
                        lactation_hit_count=len(lactation_agents),
                        dual_hit_count=len(dual_hit_agents),
                        pregnancy_agents=pregnancy_agents,
                        lactation_agents=lactation_agents,
                        dual_hit_agents=dual_hit_agents,
                        medication_names=[
                            med_by_agent[a] for a in sensitive if a in med_by_agent
                        ],
                        trimester=normalized_trimester,
                        severity=Severity.HIGH,
                        rationale=(
                            "RESEARCH USE ONLY: Trimester context amplification — "
                            f"trimester {normalized_trimester} with trimester-sensitive "
                            f"agents {', '.join(sensitive)} (ACE/ARB/tetracycline class). "
                            "Panel-level context distinct from PregnancyLactationChecker. "
                            "Confirm with a qualified clinician; prefer GPT-5.5 / "
                            "Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                        ),
                    )
                )

        findings.sort(
            key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind)
        )
        logger.info("pregnancy_lactation_risk_panel_checked", findings=len(findings))
        return findings

    @staticmethod
    def _normalize_trimester(trimester: str | None) -> str | None:
        """Normalize trimester aliases to '1', '2', or '3'."""
        if trimester is None:
            return None
        key = trimester.strip().lower()
        return _TRIMESTER_ALIASES.get(key)

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
