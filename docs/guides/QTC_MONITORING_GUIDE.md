# QTc Monitoring Interval Checker Guide

*medagent-core — Safety Control #31*

![QTc monitoring checker flow](../../assets/qtc_monitoring_demo.gif)

## Overview

`QtcMonitoringChecker` flags when **ECG/QTc monitoring is missing or overdue**
for high-risk QT-prolonging medications — a clinical decision-support gap versus
UpToDate/Lexicomp-style QTc surveillance cadence. It complements
`QTProlongationChecker` (additive QT exposure) and `QtcDdiChecker` (named
synergistic pairs) by focusing on whether periodic ECG review is adequate.

Findings are advisory `QtcMonitoringRisk` records — **RESEARCH USE ONLY** — and
the checker is exported from `medagent.safety`.

## Monitoring thresholds

| Phase | Interval | When applied |
|---|---|---|
| Initiation | ≤ **7 days** | `on_initiation=True` (therapy start or dose titration) |
| Maintenance | ≤ **30 days** | default (`on_initiation=False`) |

A finding is emitted when `last_ecg_days_ago` is **unknown/missing** or **exceeds**
the interval for the active phase.

## Curated high-risk panel

| Category | Agents / conditions | Typical severity |
|---|---|---|
| Class III antiarrhythmic | dofetilide, sotalol, amiodarone | CRITICAL / HIGH |
| Class Ia antiarrhythmic | quinidine, procainamide | CRITICAL / HIGH |
| Opioid | methadone | HIGH |
| Antipsychotic | haloperidol, ziprasidone, thioridazine | HIGH |
| SSRI (high dose) | citalopram **>40 mg**, escitalopram **>20 mg** | HIGH |
| Antiemetic (IV) | ondansetron IV / injection | HIGH |

Medication matching is whole-token based: `Pseudosotalol` does not match
`sotalol`. High-dose SSRIs require a parseable `mg` dose in the medication name.
IV ondansetron is detected by `iv`, `intravenous`, or `injection` cues.

Baseline QTc (`baseline_qtc_ms`) is optional. Values ≥480 ms are noted in the
rationale; values ≥500 ms elevate non-CRITICAL findings to CRITICAL.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import QtcMonitoringChecker

findings = QtcMonitoringChecker().check(
    medications=[
        Medication(name="Sotalol 80mg BID"),
        Medication(name="Citalopram 60mg daily"),
    ],
    last_ecg_days_ago=45,
    baseline_qtc_ms=492.0,
    on_initiation=False,
)
for finding in findings:
    print(
        finding.agent,
        finding.monitoring_phase,
        finding.recommended_interval_days,
        finding.severity,
        finding.rationale,
    )
```

## Reasoning stack notes

When this checker’s findings are summarized by an upstream reasoning / routing
layer, prefer current frontier models for clinical prose:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.31](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Additive QT checker: `safety/qt_prolongation_checker.py`
- QTc DDI panel: `safety/qtc_ddi_checker.py`
