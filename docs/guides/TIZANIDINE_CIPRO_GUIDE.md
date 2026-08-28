# Tizanidine + Strong CYP1A2 Inhibitor Hypotension / Sedation Checker

*medagent-core — Safety Control #103*

![tizanidine cipro checker flow](../../assets/tizanidine_cipro_demo.gif)

## Overview

`TizanidineCiproChecker` flags tizanidine therapy (tizanidine, Zanaflex) co-prescribed with strong CYP1A2 inhibitors (ciprofloxacin/Cipro or fluvoxamine/Luvox — `CRITICAL`). Strong CYP1A2 inhibition can markedly elevate tizanidine exposure and precipitate profound hypotension and sedation.

Findings are advisory `TizanidineCiproRisk` records — **RESEARCH USE ONLY**. The checker is exported from `medagent.safety`. This tizanidine-focused CYP1A2 control is distinct from theophylline + cipro (`theophylline_cipro_checker.py`) and clozapine CYP1A2 (`clozapine_cyp1a2_checker.py`) checks.

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| Tizanidine | tizanidine, zanaflex | — |
| Strong CYP1A2 inhibitor | ciprofloxacin, cipro, fluvoxamine, luvox | `CRITICAL` |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic (severity-first, then medication name).

## Quick start

```python
from medagent.models import Medication
from medagent.safety import TizanidineCiproChecker

findings = TizanidineCiproChecker().check(
    [
        Medication(name="Tizanidine 4 mg TID"),
        Medication(name="Ciprofloxacin 500 mg BID"),
    ]
)
```

## Scope boundaries

This is a **tizanidine × strong CYP1A2 inhibitor** control, distinct from theophylline + ciprofloxacin and clozapine + CYP1A2 screens. The control does not replace hemodynamic monitoring or urgent qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.103](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Theophylline + cipro: `safety/theophylline_cipro_checker.py`
- Clozapine CYP1A2: `safety/clozapine_cyp1a2_checker.py`
- Generic interaction validation: `retrieval/drug_sources.py`
