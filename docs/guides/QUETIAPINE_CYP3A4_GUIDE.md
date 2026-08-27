# Quetiapine + Strong CYP3A4 Inhibitor QT / Sedation Exposure Checker

*medagent-core — Safety Control #100*

![quetiapine CYP3A4 checker flow](../../assets/quetiapine_cyp3a4_demo.gif)

## Overview

`QuetiapineCyp3a4Checker` flags quetiapine therapy (Seroquel) co-prescribed with strong CYP3A4 inhibitors (ketoconazole, itraconazole, ritonavir, cobicistat — `CRITICAL`; clarithromycin — `HIGH`). Strong CYP3A4 inhibition can markedly increase quetiapine exposure and intensify QT-prolongation and sedation risk.

Findings are advisory `QuetiapineCyp3a4Risk` records — **RESEARCH USE ONLY**. The checker is exported from `medagent.safety`. This quetiapine-focused CYP3A4 control is distinct from colchicine CYP3A4/P-gp (`colchicine_cyp3a4_checker.py`) and fentanyl CYP3A4 (`fentanyl_cyp3a4_checker.py`) checks.

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| Quetiapine | quetiapine, seroquel | — |
| Strong CYP3A4 inhibitor | ketoconazole, itraconazole, ritonavir, cobicistat | `CRITICAL` |
| Strong CYP3A4 inhibitor | clarithromycin | `HIGH` |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic (severity-first, then medication name).

## Quick start

```python
from medagent.models import Medication
from medagent.safety import QuetiapineCyp3a4Checker

findings = QuetiapineCyp3a4Checker().check(
    [
        Medication(name="Quetiapine 200 mg BID"),
        Medication(name="Ketoconazole 200 mg"),
    ]
)
```

## Scope boundaries

This is a **quetiapine-focused CYP3A4** control, distinct from colchicine CYP3A4/P-gp and fentanyl CYP3A4 exposure screening. Moderate or weak inhibitors remain out of scope. The control does not replace ECG/sedation assessment or urgent qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.100](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Colchicine CYP3A4/P-gp: `safety/colchicine_cyp3a4_checker.py`
- Fentanyl CYP3A4: `safety/fentanyl_cyp3a4_checker.py`
- Generic interaction validation: `retrieval/drug_sources.py`
