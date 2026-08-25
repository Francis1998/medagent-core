# Valproate + Carbapenem Precipitous Level-Drop Checker

*medagent-core — Safety Control #92*

![valproate carbapenem checker flow](../../assets/valproate_carbapenem_demo.gif)

## Overview

`ValproateCarbapenemChecker` flags valproate therapy (valproic acid, divalproex, Depakote, Depakene) co-prescribed with a carbapenem antibiotic (meropenem, ertapenem, imipenem, doripenem, carbapenem). Carbapenems can cause a precipitous drop in serum valproate levels, increasing breakthrough seizure risk.

Findings are advisory `ValproateCarbapenemRisk` records — **RESEARCH USE ONLY** — with **CRITICAL** severity. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| Valproate | valproate, valproic acid, divalproex, depakote, depakene | — |
| Carbapenem partner | meropenem, ertapenem, imipenem, doripenem, carbapenem | `CRITICAL` |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic (severity-first, then medication name).

## Quick start

```python
from medagent.models import Medication
from medagent.safety import ValproateCarbapenemChecker

findings = ValproateCarbapenemChecker().check(
    [
        Medication(name="Depakote 500 mg"),
        Medication(name="Meropenem 1 g"),
    ]
)
```

## Scope boundaries

This is a **valproate × carbapenem** control, distinct from general AED interaction screens and from the lamotrigine × valproate SJS/TEN checker. Non-carbapenem beta-lactams remain out of scope. The control does not replace medication reconciliation, therapeutic drug monitoring, or qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.92](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Generic interaction validation: `retrieval/drug_sources.py`
