# Clozapine + Strong CYP1A2 Inhibitor Exposure Checker

*medagent-core — Safety Control #96*

![clozapine CYP1A2 checker flow](../../assets/clozapine_cyp1a2_demo.gif)

## Overview

`ClozapineCyp1a2Checker` flags clozapine therapy (Clozaril, FazaClo, Versacloz) co-prescribed with strong CYP1A2 inhibitors. Fluvoxamine/Luvox is `CRITICAL`; ciprofloxacin/Cipro is `HIGH`. Strong CYP1A2 inhibition can markedly elevate clozapine serum levels and increase seizure and myocarditis risk.

Findings are advisory `ClozapineCyp1a2Risk` records — **RESEARCH USE ONLY**. The checker is exported from `medagent.safety`. This focused CYP1A2 control is distinct from the clozapine ANC monitoring checker (`clozapine_anc_checker.py`).

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| Clozapine | clozapine, clozaril, fazaclo, versacloz | — |
| Strong CYP1A2 inhibitor | fluvoxamine, luvox | `CRITICAL` |
| Strong CYP1A2 inhibitor | ciprofloxacin, cipro | `HIGH` |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic (severity-first, then medication name).

## Quick start

```python
from medagent.models import Medication
from medagent.safety import ClozapineCyp1a2Checker

findings = ClozapineCyp1a2Checker().check(
    [
        Medication(name="Clozapine 100 mg"),
        Medication(name="Fluvoxamine 100 mg"),
    ]
)
```

## Scope boundaries

This is a **clozapine-focused CYP1A2** control, distinct from clozapine ANC monitoring (`clozapine_anc_checker.py`) and theophylline + ciprofloxacin CYP1A2 screening. Other antipsychotics and weaker CYP1A2 inhibitors remain out of scope. The control does not replace therapeutic drug monitoring, cardiac evaluation, or qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.96](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Clozapine ANC monitoring: `safety/clozapine_anc_checker.py`
- Theophylline + ciprofloxacin: `safety/theophylline_cipro_checker.py`
- Generic interaction validation: `retrieval/drug_sources.py`
