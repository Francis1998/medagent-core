# Methotrexate + NSAID Reduced-Clearance Toxicity Checker

*medagent-core — Safety Control #101*

![methotrexate nsaid checker flow](../../assets/methotrexate_nsaid_demo.gif)

## Overview

`MethotrexateNsaidChecker` flags methotrexate therapy (methotrexate, Trexall, Otrexup, Rasuvo, Xatmep) co-prescribed with NSAIDs (ibuprofen, naproxen, diclofenac, indomethacin, meloxicam, celecoxib, or generic NSAID — `HIGH`; ketorolac — `CRITICAL`). NSAIDs can reduce methotrexate clearance and increase toxicity risk.

Findings are advisory `MethotrexateNsaidRisk` records — **RESEARCH USE ONLY**. The checker is exported from `medagent.safety`. This brand-aware control is distinct from the legacy `mtx_nsaid_checker.py`, methotrexate + TMP-SMX, and other NSAID bleed-risk checks.

## Medication panels

| Class | Agents | Severity |
|---|---|---|
| Methotrexate | methotrexate, trexall, otrexup, rasuvo, xatmep | — |
| NSAID | ketorolac | `CRITICAL` |
| NSAID | ibuprofen, naproxen, diclofenac, indomethacin, meloxicam, celecoxib, nsaid | `HIGH` |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic (severity-first, then medication name).

## Quick start

```python
from medagent.models import Medication
from medagent.safety import MethotrexateNsaidChecker

findings = MethotrexateNsaidChecker().check(
    [
        Medication(name="Methotrexate 15 mg weekly"),
        Medication(name="Ketorolac 10 mg q6h"),
    ]
)
```

## Scope boundaries

This is a **methotrexate × NSAID** control, distinct from methotrexate + TMP-SMX antifolate synergy and warfarin/lithium NSAID bleed or lithium-level screens. The control does not replace lab monitoring or urgent qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.101](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Legacy MTX + NSAID: `safety/mtx_nsaid_checker.py`
- Methotrexate + TMP-SMX: `safety/mtx_tmpsmx_checker.py`
- Generic interaction validation: `retrieval/drug_sources.py`
