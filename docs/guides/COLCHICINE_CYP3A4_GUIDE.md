# Colchicine + Strong CYP3A4/P-gp Inhibitor Toxicity Checker

*medagent-core — Safety Control #95*

![colchicine CYP3A4/P-gp checker flow](../../assets/colchicine_cyp3a4_demo.gif)

## Overview

`ColchicineCyp3a4Checker` flags colchicine-class therapy (Colcrys, Mitigare, Gloperba) co-prescribed with strong CYP3A4 and/or P-glycoprotein inhibitors (clarithromycin, ketoconazole, itraconazole, ritonavir, cyclosporine/ciclosporin, cobicistat, posaconazole). Strong dual-pathway inhibition can markedly increase colchicine exposure and cause severe or fatal toxicity (FDA boxed-warning territory). All supported pairs are `CRITICAL`.

Findings are advisory `ColchicineCyp3a4Risk` records — **RESEARCH USE ONLY**. The checker is exported from `medagent.safety`. This colchicine-focused control is distinct from the fentanyl CYP3A4 exposure checker (`fentanyl_cyp3a4_checker.py`).

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| Colchicine | colchicine, colcrys, mitigare, gloperba | — |
| Strong CYP3A4/P-gp inhibitor | clarithromycin, ketoconazole, itraconazole, ritonavir, cyclosporine, ciclosporin, cobicistat, posaconazole | `CRITICAL` |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic (severity-first, then medication name).

## Quick start

```python
from medagent.models import Medication
from medagent.safety import ColchicineCyp3a4Checker

findings = ColchicineCyp3a4Checker().check(
    [
        Medication(name="Colchicine 0.6 mg daily"),
        Medication(name="Clarithromycin 500 mg BID"),
    ]
)
```

## Scope boundaries

This is a **colchicine-focused CYP3A4/P-gp** control, distinct from fentanyl CYP3A4 exposure (`fentanyl_cyp3a4_checker.py`) and general statin CYP3A4 screening. Moderate or weak inhibitors remain out of scope. The control does not replace renal/hepatic assessment, toxicity evaluation, or urgent qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.95](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Fentanyl CYP3A4 exposure: `safety/fentanyl_cyp3a4_checker.py`
- Broad CYP3A4 control: `safety/statin_cyp3a4_checker.py`
- Generic interaction validation: `retrieval/drug_sources.py`
