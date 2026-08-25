# Lamotrigine + Valproate SJS/TEN Risk Checker

*medagent-core — Safety Control #93*

![lamotrigine valproate checker flow](../../assets/lamotrigine_valproate_demo.gif)

## Overview

`LamotrigineValproateChecker` flags lamotrigine therapy (lamotrigine, Lamictal) co-prescribed with a valproate agent (valproate, valproic acid, divalproex, Depakote). Valproate inhibits lamotrigine metabolism, raising exposure and the risk of serious cutaneous reactions including SJS/TEN.

Findings are advisory `LamotrigineValproateRisk` records — **RESEARCH USE ONLY** — with **CRITICAL** severity. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| Lamotrigine | lamotrigine, lamictal | — |
| Valproate partner | valproate, valproic acid, divalproex, depakote | `CRITICAL` |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic (severity-first, then medication name).

## Quick start

```python
from medagent.models import Medication
from medagent.safety import LamotrigineValproateChecker

findings = LamotrigineValproateChecker().check(
    [
        Medication(name="Lamictal 25 mg"),
        Medication(name="Depakote 500 mg"),
    ]
)
```

## Scope boundaries

This is a **lamotrigine × valproate** control focused on SJS/TEN risk from inhibited lamotrigine clearance. It is distinct from the valproate × carbapenem precipitous level-drop checker and from general AED screens. The control does not replace titration guidance, medication reconciliation, or qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.93](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Generic interaction validation: `retrieval/drug_sources.py`
