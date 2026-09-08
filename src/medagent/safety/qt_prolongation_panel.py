"""QT prolongation panel - aggregate multi-drug torsades risk summary.

The existing :class:`~medagent.safety.qt_prolongation_checker.QTProlongationChecker`
emits **per-medication** QT findings (with a simple additive count), and
:class:`~medagent.safety.qtc_ddi_checker.QtcDdiChecker` emits **named pairwise**
synergistic QTc interactions. Neither produces a single panel-level aggregate
that summarises distinct agents, pharmacologic classes, and optional QTc /
electrolyte context together.

This panel fills that gap: it aggregates matching QT-prolonging agents across
the medication list into advisory :class:`~medagent.models.QtPanelRisk`
findings (multi-agent load, same-class clustering, optional prolonged QTc /
low-electrolyte context). Findings are RESEARCH USE ONLY and never modify
medications.
"""

from __future__ import annotations

import re
from typing import Final

from medagent.logging_config import get_logger
from medagent.models import Medication, QtPanelRisk, Severity

logger = get_logger(__name__)

_SEVERITY_RANK: Final[dict[Severity, int]] = {
    Severity.UNKNOWN: 0,
    Severity.LOW: 1,
    Severity.MODERATE: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

# Canonical agent -> (class_label, baseline severity, short reason)
_PANEL: Final[dict[str, tuple[str, Severity, str]]] = {
    "amiodarone": ("antiarrhythmic", Severity.HIGH, "class III antiarrhythmic"),
    "sotalol": ("antiarrhythmic", Severity.HIGH, "class III antiarrhythmic"),
    "dofetilide": ("antiarrhythmic", Severity.HIGH, "class III antiarrhythmic"),
    "quinidine": ("antiarrhythmic", Severity.HIGH, "class Ia antiarrhythmic"),
    "procainamide": ("antiarrhythmic", Severity.HIGH, "class Ia antiarrhythmic"),
    "methadone": ("opioid", Severity.HIGH, "long-acting opioid with QT risk"),
    "haloperidol": ("antipsychotic", Severity.MODERATE, "antipsychotic QT risk"),
    "thioridazine": ("antipsychotic", Severity.HIGH, "antipsychotic with marked QT risk"),
    "ziprasidone": ("antipsychotic", Severity.MODERATE, "antipsychotic QT risk"),
    "citalopram": ("ssri", Severity.MODERATE, "SSRI with dose-dependent QT risk"),
    "escitalopram": ("ssri", Severity.MODERATE, "SSRI QT risk"),
    "azithromycin": ("macrolide", Severity.MODERATE, "macrolide QT risk"),
    "clarithromycin": ("macrolide", Severity.MODERATE, "macrolide QT risk"),
    "erythromycin": ("macrolide", Severity.MODERATE, "macrolide QT risk"),
    "moxifloxacin": ("fluoroquinolone", Severity.MODERATE, "fluoroquinolone QT risk"),
    "levofloxacin": ("fluoroquinolone", Severity.MODERATE, "fluoroquinolone QT risk"),
    "ciprofloxacin": ("fluoroquinolone", Severity.LOW, "fluoroquinolone QT risk"),
    "ondansetron": ("antiemetic", Severity.MODERATE, "antiemetic QT risk"),
    "fluconazole": ("azole", Severity.MODERATE, "azole antifungal QT risk"),
}


class QtProlongationPanel:
    """Aggregate multi-drug QT risk into panel-level advisory findings."""

    def check(
        self,
        medications: list[Medication],
        *,
        qtc_ms: float | None = None,
        potassium_mmol_l: float | None = None,
        magnesium_mg_dl: float | None = None,
    ) -> list[QtPanelRisk]:
        """Return aggregate QT panel findings for the active medication list.

        Args:
            medications: Active patient medications.
            qtc_ms: Optional measured QTc in milliseconds.
            potassium_mmol_l: Optional serum potassium in mmol/L.
            magnesium_mg_dl: Optional serum magnesium in mg/dL.

        Returns:
            Zero or more :class:`QtPanelRisk` findings summarising multi-agent
            QT load, same-class clustering, and optional QTc/electrolyte
            context. Distinct from per-drug :class:`QTProlongationChecker`
            findings and named-pair :class:`QtcDdiChecker` findings.
        """
        matched: list[tuple[str, str, str, Severity, str]] = []
        # (medication_name, agent, class_label, severity, reason)
        seen_agents: set[str] = set()
        for medication in medications:
            tokens = self._tokens(medication.name)
            agents = sorted(tokens & set(_PANEL))
            for agent in agents:
                if agent in seen_agents:
                    continue
                class_label, severity, reason = _PANEL[agent]
                matched.append((medication.name, agent, class_label, severity, reason))
                seen_agents.add(agent)

        if not matched:
            logger.info("qt_prolongation_panel_checked", findings=0)
            return []

        findings: list[QtPanelRisk] = []
        agents = [agent for _med, agent, _cls, _sev, _reason in matched]
        classes = sorted({cls for _med, _agent, cls, _sev, _reason in matched})
        med_names = [med for med, _agent, _cls, _sev, _reason in matched]
        max_baseline = max(matched, key=lambda item: _SEVERITY_RANK[item[3]])[3]

        # Multi-agent aggregate when 2+ distinct QT agents.
        if len(matched) >= 2:
            severity = Severity.HIGH if len(matched) >= 3 else Severity.MODERATE
            if _SEVERITY_RANK[max_baseline] >= _SEVERITY_RANK[Severity.HIGH]:
                severity = Severity.HIGH if len(matched) == 2 else Severity.CRITICAL
            findings.append(
                QtPanelRisk(
                    finding_kind="multi_agent_aggregate",
                    agents=agents,
                    medication_names=med_names,
                    pharmacologic_classes=classes,
                    agent_count=len(matched),
                    qtc_ms=qtc_ms,
                    potassium_mmol_l=potassium_mmol_l,
                    magnesium_mg_dl=magnesium_mg_dl,
                    severity=severity,
                    rationale=(
                        "RESEARCH USE ONLY: Aggregate QT panel detected "
                        f"{len(matched)} distinct QT-prolonging agents "
                        f"({', '.join(agents)}) across classes "
                        f"{', '.join(classes)}. This summarises multi-drug "
                        "torsades load and is distinct from per-drug "
                        "QTProlongationChecker findings and named-pair "
                        "QtcDdiChecker pairs. Not a prescription. Confirm with "
                        "a qualified clinician; prefer frontier summarization "
                        "with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                    ),
                )
            )

        # Same-class clustering (2+ agents sharing a pharmacologic class).
        by_class: dict[str, list[str]] = {}
        for _med, agent, class_label, _sev, _reason in matched:
            by_class.setdefault(class_label, []).append(agent)
        for class_label, class_agents in sorted(by_class.items()):
            if len(class_agents) < 2:
                continue
            findings.append(
                QtPanelRisk(
                    finding_kind="same_class_cluster",
                    agents=class_agents,
                    medication_names=[
                        med for med, agent, cls, _sev, _reason in matched if cls == class_label
                    ],
                    pharmacologic_classes=[class_label],
                    agent_count=len(class_agents),
                    qtc_ms=qtc_ms,
                    potassium_mmol_l=potassium_mmol_l,
                    magnesium_mg_dl=magnesium_mg_dl,
                    severity=Severity.HIGH,
                    rationale=(
                        "RESEARCH USE ONLY: QT panel same-class cluster for "
                        f"'{class_label}' with agents {', '.join(class_agents)}. "
                        "Class stacking can amplify torsades risk beyond a single "
                        "named DDI pair. Distinct from QTProlongationChecker and "
                        "QtcDdiChecker. Confirm with a qualified clinician; prefer "
                        "GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."
                    ),
                )
            )

        # Optional context: prolonged QTc or low electrolytes with any QT agent.
        context_bits: list[str] = []
        context_severity = Severity.MODERATE
        if qtc_ms is not None and qtc_ms >= 500:
            context_bits.append(f"QTc {qtc_ms:g} ms (≥500)")
            context_severity = Severity.CRITICAL
        elif qtc_ms is not None and qtc_ms >= 470:
            context_bits.append(f"QTc {qtc_ms:g} ms (≥470)")
            context_severity = Severity.HIGH
        if potassium_mmol_l is not None and potassium_mmol_l < 3.5:
            context_bits.append(f"K {potassium_mmol_l:g} mmol/L (<3.5)")
            if _SEVERITY_RANK[context_severity] < _SEVERITY_RANK[Severity.HIGH]:
                context_severity = Severity.HIGH
        if magnesium_mg_dl is not None and magnesium_mg_dl < 1.7:
            context_bits.append(f"Mg {magnesium_mg_dl:g} mg/dL (<1.7)")
            if _SEVERITY_RANK[context_severity] < _SEVERITY_RANK[Severity.HIGH]:
                context_severity = Severity.HIGH

        if context_bits and matched:
            findings.append(
                QtPanelRisk(
                    finding_kind="context_amplified",
                    agents=agents,
                    medication_names=med_names,
                    pharmacologic_classes=classes,
                    agent_count=len(matched),
                    qtc_ms=qtc_ms,
                    potassium_mmol_l=potassium_mmol_l,
                    magnesium_mg_dl=magnesium_mg_dl,
                    severity=context_severity,
                    rationale=(
                        "RESEARCH USE ONLY: QT panel context amplification - "
                        f"{'; '.join(context_bits)} with QT agents "
                        f"{', '.join(agents)}. Aggregates medication + lab/ECG "
                        "context beyond per-drug QTProlongationChecker / "
                        "qtc_ddi pairs. Confirm with a qualified clinician; "
                        "prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / "
                        "Kimi K2."
                    ),
                )
            )

        # Single-agent panel note when only one QT agent and no context finding.
        if len(matched) == 1 and not context_bits:
            med, agent, class_label, severity, reason = matched[0]
            findings.append(
                QtPanelRisk(
                    finding_kind="single_agent_panel",
                    agents=[agent],
                    medication_names=[med],
                    pharmacologic_classes=[class_label],
                    agent_count=1,
                    qtc_ms=qtc_ms,
                    potassium_mmol_l=potassium_mmol_l,
                    magnesium_mg_dl=magnesium_mg_dl,
                    severity=severity,
                    rationale=(
                        "RESEARCH USE ONLY: QT panel single-agent entry for "
                        f"'{agent}' ({reason}, class '{class_label}') on "
                        f"medication '{med}'. Panel-level registry distinct "
                        "from per-drug checker detail. Confirm with a qualified "
                        "clinician; prefer GPT-5.5 / Claude Sonnet 4.6 / "
                        "Gemini 3.x / Kimi K2."
                    ),
                )
            )

        findings.sort(key=lambda finding: (-_SEVERITY_RANK[finding.severity], finding.finding_kind))
        logger.info("qt_prolongation_panel_checked", findings=len(findings))
        return findings

    @staticmethod
    def _tokens(name: str) -> set[str]:
        """Return lowercase alphanumeric whole-token set."""
        return set(re.findall(r"[a-z0-9]+", name.lower()))
