# Warfarin + TMP-SMX INR Elevation / Bleed Risk Checker

*medagent-core — Safety Control #99*

![warfarin TMP-SMX checker flow](../../assets/warfarin_tmpsmx_demo.gif)

## Overview

`WarfarinTmpsmxChecker` flags warfarin therapy (Coumadin, Jantoven) co-prescribed with TMP-SMX / trimethoprim–sulfamethoxazole (trimethoprim, sulfamethoxazole, Bactrim, Septra, cotrimoxazole, TMP-SMX). TMP-SMX can potentiate warfarin anticoagulation, elevate INR, and increase major bleeding risk. All supported pairs are `CRITICAL`.

Findings are advisory `WarfarinTmpsmxRisk` records — **RESEARCH USE ONLY**. The checker is exported from `medagent.safety`. This warfarin × TMP-SMX control is distinct from methotrexate + TMP-SMX (`mtx_tmpsmx_checker.py`) and fluoroquinolone + warfarin (`fluoroquinolone_warfarin_checker.py`) checks.

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| Warfarin | warfarin, coumadin, jantoven | — |
| TMP-SMX | trimethoprim, sulfamethoxazole, bactrim, septra, cotrimoxazole, tmp-smx, trimethoprim-sulfamethoxazole | `CRITICAL` |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic (severity-first, then medication name).

## Quick start

```python
from medagent.models import Medication
from medagent.safety import WarfarinTmpsmxChecker

findings = WarfarinTmpsmxChecker().check(
    [
        Medication(name="Warfarin 5 mg daily"),
        Medication(name="Bactrim DS BID"),
    ]
)
```

## Scope boundaries

This is a **warfarin × TMP-SMX** control, distinct from methotrexate + TMP-SMX toxicity and fluoroquinolone + warfarin INR screening. The control does not replace INR monitoring or urgent qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.99](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Methotrexate + TMP-SMX: `safety/mtx_tmpsmx_checker.py`
- Fluoroquinolone + warfarin: `safety/fluoroquinolone_warfarin_checker.py`
- Generic interaction validation: `retrieval/drug_sources.py`
