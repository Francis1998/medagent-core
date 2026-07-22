# QTc DDI Checker Guide

*medagent-core — Safety Control #24*

![QTc DDI checker flow](../../assets/qtc_ddi_demo.gif)

## Overview

`QtcDdiChecker` flags a conservative panel of named **QTc-prolonging
drug-drug interaction pairs** whose risk is more specific than a generic count
of QT-prolonging agents. It complements `QTProlongationChecker`: the existing
checker identifies additive exposure across QT-prolonging medications, while
this panel highlights combinations with known synergistic torsades risk such as
**methadone + ondansetron** and **azithromycin + amiodarone**.

Findings are advisory `QtcDdiRisk` records — RESEARCH USE ONLY. The checker is
deterministic, uses whole-token medication matching, de-duplicates duplicate
same-agent entries, and is exported from `medagent.safety` for direct callers.

## Curated high-risk panel

| Pair id | Agents | Severity | Risk theme |
|---|---|---|---|
| QTC-DDI-001 | azithromycin + amiodarone | CRITICAL | macrolide QTc effect + class III antiarrhythmic |
| QTC-DDI-002 | clarithromycin + amiodarone | CRITICAL | CYP3A4 inhibition + additive QTc prolongation |
| QTC-DDI-003 | erythromycin + amiodarone | CRITICAL | macrolide QTc effect/CYP inhibition + amiodarone |
| QTC-DDI-004 | methadone + ondansetron | HIGH | dose-dependent opioid QTc effect + 5-HT3 antagonist |
| QTC-DDI-005 | methadone + azithromycin | HIGH | methadone repolarization delay + macrolide QTc effect |
| QTC-DDI-006 | sotalol + azithromycin | CRITICAL | class III antiarrhythmic + macrolide QTc effect |
| QTC-DDI-007 | dofetilide + azithromycin | CRITICAL | high-risk antiarrhythmic + macrolide QTc effect |
| QTC-DDI-008 | haloperidol + azithromycin | HIGH | antipsychotic + macrolide repolarization effects |
| QTC-DDI-009 | citalopram + ondansetron | HIGH | SSRI QTc effect + 5-HT3 antagonist |
| QTC-DDI-010 | amiodarone + moxifloxacin | CRITICAL | class III antiarrhythmic + fluoroquinolone QTc effect |
| QTC-DDI-011 | fluconazole + amiodarone | HIGH | azole QTc/CYP effect layered on amiodarone |

Matching is whole-token based: `pseudoazithromycin` does not match
`azithromycin`, and loose substrings never trigger a finding.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import QtcDdiChecker

findings = QtcDdiChecker().check(
    medications=[
        Medication(name="Amiodarone 200 mg"),
        Medication(name="Azithromycin Z-Pak"),
        Medication(name="Ondansetron 8 mg PRN"),
    ],
)
for finding in findings:
    print(
        finding.pair_id,
        finding.agent_a,
        finding.agent_b,
        finding.severity,
        finding.mechanism,
    )
```

## Reasoning stack notes

When this checker’s findings are summarized by an upstream reasoning / routing
layer, prefer current frontier models for clinical prose:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 2.5**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.24](../../SAFETY.md)
- [README safety controls table](../../README.md)
- [CHANGELOG](../../CHANGELOG.md)
- Additive QT checker: `safety/qt_prolongation_checker.py`
