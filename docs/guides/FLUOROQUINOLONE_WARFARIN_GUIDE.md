# Fluoroquinolone + Warfarin INR/Bleeding Checker Guide

*medagent-core — Safety Control #59*

![Fluoroquinolone warfarin checker flow](../../assets/fluoroquinolone_warfarin_demo.gif)

## Overview

`FluoroquinoloneWarfarinChecker` flags ciprofloxacin, levofloxacin,
moxifloxacin, or ofloxacin co-prescribed with warfarin, Coumadin, or Jantoven.
Fluoroquinolones can potentiate warfarin anticoagulation, increasing INR
variability and bleeding risk.

Findings are advisory `FluoroquinoloneWarfarinRisk` records —
**RESEARCH USE ONLY** — and the checker is exported from `medagent.safety`.
Severity is always **HIGH**.

## Fluoroquinolone panel

| Agent | Notes |
|---|---|
| ciprofloxacin | fluoroquinolone antibiotic |
| levofloxacin | fluoroquinolone antibiotic |
| moxifloxacin | fluoroquinolone antibiotic |
| ofloxacin | fluoroquinolone antibiotic |

## Warfarin-class partners

| Agent | Notes |
|---|---|
| warfarin | vitamin K antagonist |
| coumadin | warfarin brand |
| jantoven | warfarin brand |

Every unique fluoroquinolone × warfarin-class pair across separate medication
entries yields one finding. Matching is whole-token based, duplicates are
de-duplicated by canonical pair, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import FluoroquinoloneWarfarinChecker

findings = FluoroquinoloneWarfarinChecker().check(
    medications=[
        Medication(name="Ciprofloxacin 500 mg BID"),
        Medication(name="Warfarin 5 mg daily"),
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

This control targets the fluoroquinolone × warfarin INR/bleeding interaction.
It does not replace the amiodarone + warfarin or warfarin + NSAID controls,
generic interaction screening, INR measurement, or qualified clinical review.
It never changes medication or monitoring plans.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.59](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Amiodarone + warfarin: `safety/amio_warfarin_checker.py`
- Warfarin + NSAID: `safety/warfarin_nsaid_checker.py`
