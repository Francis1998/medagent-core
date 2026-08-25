# Fentanyl + CYP3A4 Inhibitor Exposure Checker

*medagent-core — Safety Control #94*

![fentanyl CYP3A4 checker flow](../../assets/fentanyl_cyp3a4_demo.gif)

## Overview

`FentanylCyp3a4Checker` flags fentanyl therapy (Duragesic, Abstral, Fentora, Actiq) co-prescribed with a CYP3A4 inhibitor. Strong inhibitors (ketoconazole, itraconazole, ritonavir, clarithromycin, nefazodone) are `CRITICAL`; moderate inhibitors (erythromycin, fluconazole, diltiazem, verapamil) are `HIGH`. CYP3A4 inhibition raises fentanyl exposure and respiratory-depression risk.

Findings are advisory `FentanylCyp3a4Risk` records — **RESEARCH USE ONLY**. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| Fentanyl | fentanyl, duragesic, abstral, fentora, actiq | — |
| Strong CYP3A4 inhibitor | ketoconazole, itraconazole, ritonavir, clarithromycin, nefazodone | `CRITICAL` |
| Moderate CYP3A4 inhibitor | erythromycin, fluconazole, diltiazem, verapamil | `HIGH` |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic (severity-first, then medication name).

## Quick start

```python
from medagent.models import Medication
from medagent.safety import FentanylCyp3a4Checker

findings = FentanylCyp3a4Checker().check(
    [
        Medication(name="Fentanyl patch 25 mcg"),
        Medication(name="Ketoconazole 200 mg"),
    ]
)
```

## Scope boundaries

This is a **fentanyl-focused CYP3A4** control, distinct from opioid + benzodiazepine CNS-depression (`opioid_benzo_checker.py`) and general opioid MED checking (`opioid_med_checker.py`). Weak or out-of-panel CYP inhibitors remain out of scope. The control does not replace medication reconciliation, respiratory monitoring, or qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.94](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Opioid + benzodiazepine: `safety/opioid_benzo_checker.py`
- Generic interaction validation: `retrieval/drug_sources.py`
