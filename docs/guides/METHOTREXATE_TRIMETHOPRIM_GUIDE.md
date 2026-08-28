# Methotrexate + Trimethoprim / TMP-SMX Antifolate Synergy Checker

*medagent-core — Safety Control #102*

![methotrexate trimethoprim checker flow](../../assets/methotrexate_trimethoprim_demo.gif)

## Overview

`MethotrexateTrimethoprimChecker` flags methotrexate therapy (methotrexate, Trexall, Otrexup, Rasuvo, Xatmep) co-prescribed with trimethoprim / TMP-SMX (trimethoprim, TMP-SMX, Bactrim, Septra, co-trimoxazole, trimethoprim-sulfamethoxazole — `CRITICAL`). Trimethoprim intensifies antifolate synergy and can precipitate pancytopenia.

Findings are advisory `MethotrexateTrimethoprimRisk` records — **RESEARCH USE ONLY**. The checker is exported from `medagent.safety`. This brand-aware control is distinct from the legacy `mtx_tmpsmx_checker.py` and warfarin + TMP-SMX INR checks.

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| Methotrexate | methotrexate, trexall, otrexup, rasuvo, xatmep | — |
| Trimethoprim / TMP-SMX | trimethoprim, tmp-smx, bactrim, septra, co-trimoxazole, trimethoprim-sulfamethoxazole | `CRITICAL` |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic (severity-first, then medication name).

## Quick start

```python
from medagent.models import Medication
from medagent.safety import MethotrexateTrimethoprimChecker

findings = MethotrexateTrimethoprimChecker().check(
    [
        Medication(name="Methotrexate 15 mg weekly"),
        Medication(name="Bactrim DS BID"),
    ]
)
```

## Scope boundaries

This is a **methotrexate × trimethoprim / TMP-SMX** control, distinct from warfarin + TMP-SMX INR elevation and methotrexate + NSAID clearance toxicity. The control does not replace CBC monitoring or urgent qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.102](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Legacy MTX + TMP-SMX: `safety/mtx_tmpsmx_checker.py`
- Warfarin + TMP-SMX: `safety/warfarin_tmpsmx_checker.py`
- Generic interaction validation: `retrieval/drug_sources.py`
