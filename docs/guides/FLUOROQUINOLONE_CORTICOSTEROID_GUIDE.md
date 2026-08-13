# Fluoroquinolone + Corticosteroid Tendon Risk Checker Guide

*medagent-core — Safety Control #65*

![Fluoroquinolone corticosteroid checker flow](../../assets/fluoroquinolone_corticosteroid_demo.gif)

## Overview

`FluoroquinoloneCorticosteroidChecker` flags a fluoroquinolone antibiotic
co-prescribed with a systemic corticosteroid. Concurrent therapy increases
tendon rupture and tendinopathy risk.

Findings are advisory `FluoroquinoloneCorticosteroidRisk` records —
**RESEARCH USE ONLY** — and the checker is exported from `medagent.safety`.
Severity is always **HIGH**.

## Fluoroquinolone panel

| Agents |
|---|
| ciprofloxacin, levofloxacin, moxifloxacin, ofloxacin |

## Corticosteroid partners

| Agents |
|---|
| prednisone, prednisolone, methylprednisolone |
| dexamethasone, hydrocortisone, betamethasone |

Every unique fluoroquinolone × corticosteroid pair across separate medication
entries yields one finding. Matching is whole-token based, duplicates are
de-duplicated by canonical pair, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import FluoroquinoloneCorticosteroidChecker

findings = FluoroquinoloneCorticosteroidChecker().check(
    medications=[
        Medication(name="Ciprofloxacin 500 mg BID"),
        Medication(name="Prednisone 20 mg daily"),
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

This control targets the fluoroquinolone × corticosteroid tendon-risk pair.
Fluoroquinolone + NSAID CNS/seizure risk belongs to
`FluoroquinoloneNsaidChecker`; fluoroquinolone + warfarin INR potentiation
belongs to `FluoroquinoloneWarfarinChecker`. This control does not replace
qualified clinical review, and it never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.65](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Fluoroquinolone + NSAID: `safety/fluoroquinolone_nsaid_checker.py`
- Fluoroquinolone + warfarin: `safety/fluoroquinolone_warfarin_checker.py`
