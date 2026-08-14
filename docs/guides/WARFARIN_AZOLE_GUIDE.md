# Warfarin + Systemic Azole Antifungal Checker Guide

*medagent-core — Safety Control #68*

![Warfarin azole checker flow](../../assets/warfarin_azole_demo.gif)

## Overview

`WarfarinAzoleChecker` flags warfarin or Coumadin co-prescribed with a supported
systemic azole antifungal. Azole inhibition of CYP2C9 and other
warfarin-metabolizing CYP pathways can substantially elevate INR and bleeding
risk.

Findings are advisory `WarfarinAzoleRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents |
|---|---|
| Warfarin | warfarin, coumadin |
| Systemic azole | fluconazole, ketoconazole, itraconazole, voriconazole |

Fluconazole and voriconazole findings are **CRITICAL**. Ketoconazole and
itraconazole findings are **HIGH**. Topical clotrimazole is intentionally
excluded from this focused panel.

Every unique warfarin × azole pair across separate medication entries yields
one finding. Matching is whole-token based, duplicates are de-duplicated by
canonical pair, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import WarfarinAzoleChecker

findings = WarfarinAzoleChecker().check(
    medications=[
        Medication(name="Warfarin 5 mg daily"),
        Medication(name="Fluconazole 200 mg daily"),
    ],
)
for finding in findings:
    print(finding.agent, finding.partner_agent, finding.severity)
```

## Scope boundaries

This control targets the listed systemic azoles. It does not treat topical
clotrimazole as equivalent systemic exposure, does not replace qualified
clinical review or INR monitoring, and never changes therapy. Amiodarone,
fluoroquinolone, and NSAID interactions with warfarin remain separate controls.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.68](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Amiodarone + warfarin: `safety/amio_warfarin_checker.py`
