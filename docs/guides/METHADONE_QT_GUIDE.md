# Methadone + QT-Prolonging Drug Intensification Checker

*medagent-core — Safety Control #91*

![methadone QT checker flow](../../assets/methadone_qt_demo.gif)

## Overview

`MethadoneQtChecker` flags methadone therapy (Dolophine, Methadose) co-prescribed with another QT-prolonging medication (haloperidol, ziprasidone, ondansetron, azithromycin, citalopram, escitalopram). Methadone's own baseline QT-prolonging effect can be intensified by a second QT-prolonging agent, increasing torsades de pointes risk.

Findings are advisory `MethadoneQtRisk` records — **RESEARCH USE ONLY** — with **HIGH** or **CRITICAL** severity depending on the partner agent. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| Methadone | methadone, dolophine, methadose | — |
| QT partner | haloperidol, ziprasidone, citalopram | `CRITICAL` |
| QT partner | ondansetron, azithromycin, escitalopram | `HIGH` |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic (severity-first, then medication name).

## Quick start

```python
from medagent.models import Medication
from medagent.safety import MethadoneQtChecker

findings = MethadoneQtChecker().check(
    [
        Medication(name="Methadone 10 mg"),
        Medication(name="Haloperidol 5 mg"),
    ]
)
```

## Scope boundaries

This is a **methadone-focused intensifier** control, distinct from the general `safety/qt_prolongation_checker.py` multi-drug QT screen, which flags any combination of QT-prolonging medications rather than methadone specifically. Amiodarone, sotalol, fluoxetine, and fluoroquinolones remain out of scope for this focused panel. The control does not replace medication reconciliation, patient-specific assessment, ECG/QTc monitoring, or qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.91](../../SAFETY.md)
- [README safety controls table](../../README.md)
- General QT screening: `safety/qt_prolongation_checker.py`
- Generic interaction validation: `retrieval/drug_sources.py`
