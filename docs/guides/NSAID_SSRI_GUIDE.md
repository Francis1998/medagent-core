# NSAID + SSRI/SNRI Bleeding Intensifier Checker Guide

*medagent-core — Safety Control #61*

![NSAID SSRI/SNRI checker flow](../../assets/nsaid_ssri_demo.gif)

## Overview

`NsaidSsriBleedChecker` flags an NSAID co-prescribed with an SSRI or SNRI.
NSAID-related gastrointestinal mucosal injury and platelet inhibition combined
with SSRI/SNRI-related impairment of platelet aggregation increases
gastrointestinal and other bleeding risk.

Findings are advisory `NsaidSsriBleedRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is always
**HIGH**.

## NSAID panel

| Agents |
|---|
| ibuprofen, naproxen, diclofenac, ketorolac, meloxicam |
| celecoxib, indomethacin, piroxicam, aspirin |

## SSRI/SNRI partners

| Class | Agents |
|---|---|
| SSRI | sertraline, fluoxetine, paroxetine, citalopram, escitalopram, fluvoxamine |
| SNRI | venlafaxine, desvenlafaxine, duloxetine, levomilnacipran, milnacipran |

Every unique NSAID × SSRI/SNRI pair across separate medication entries yields
one finding. Matching is whole-token based, duplicates are de-duplicated by
canonical pair, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import NsaidSsriBleedChecker

findings = NsaidSsriBleedChecker().check(
    medications=[
        Medication(name="Ibuprofen 400 mg TID"),
        Medication(name="Sertraline 50 mg daily"),
    ],
)
for finding in findings:
    print(
        finding.agent,
        finding.partner_agent,
        finding.partner_drug_class,
        finding.severity,
        finding.rationale,
    )
```

## Scope boundaries

This control targets NSAID × SSRI/SNRI bleeding intensification. Warfarin +
NSAID belongs to `WarfarinNsaidChecker`; tramadol + SSRI/SNRI belongs to
`TramadolSsriChecker`. This control does not replace bleeding assessment or
qualified clinical review, and it never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.61](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Warfarin + NSAID: `safety/warfarin_nsaid_checker.py`
- Tramadol + SSRI/SNRI: `safety/tramadol_ssri_checker.py`
