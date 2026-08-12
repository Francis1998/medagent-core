# Fluoroquinolone + NSAID CNS / Seizure Risk Checker Guide

*medagent-core — Safety Control #62*

![Fluoroquinolone NSAID checker flow](../../assets/fluoroquinolone_nsaid_demo.gif)

## Overview

`FluoroquinoloneNsaidChecker` flags a fluoroquinolone co-prescribed with an NSAID.
Fluoroquinolones can lower the seizure threshold and cause CNS stimulation;
concurrent NSAID use intensifies that CNS / seizure risk.

Findings are advisory `FluoroquinoloneNsaidRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is always
**HIGH**.

## Fluoroquinolone panel

| Agents |
|---|
| ciprofloxacin, levofloxacin, moxifloxacin, ofloxacin |

## NSAID partners

| Agents |
|---|
| ibuprofen, naproxen, diclofenac, ketorolac, meloxicam |
| celecoxib, indomethacin, piroxicam, aspirin |

Every unique fluoroquinolone × NSAID pair across separate medication entries yields
one finding. Matching is whole-token based, duplicates are de-duplicated by
canonical pair, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import FluoroquinoloneNsaidChecker

findings = FluoroquinoloneNsaidChecker().check(
    medications=[
        Medication(name="Ciprofloxacin 500 mg BID"),
        Medication(name="Ibuprofen 400 mg TID"),
    ],
)
for finding in findings:
    print(
        finding.agent,
        finding.partner_agent,
        finding.severity,
        finding.rationale,
    )
```

## Scope boundaries

This control targets fluoroquinolone × NSAID CNS / seizure intensification.
Fluoroquinolone + warfarin belongs to `FluoroquinoloneWarfarinChecker`; warfarin +
NSAID belongs to `WarfarinNsaidChecker`. This control does not replace seizure-risk
assessment or qualified clinical review, and it never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.62](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Fluoroquinolone + warfarin: `safety/fluoroquinolone_warfarin_checker.py`
- Warfarin + NSAID: `safety/warfarin_nsaid_checker.py`
