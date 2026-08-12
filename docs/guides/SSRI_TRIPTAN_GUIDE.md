# SSRI/SNRI + Triptan Serotonin Syndrome Pair Checker Guide

*medagent-core — Safety Control #64*

![SSRI triptan checker flow](../../assets/ssri_triptan_demo.gif)

## Overview

`SsriTriptanChecker` flags an SSRI or SNRI co-prescribed with a triptan
antimigraine agent. Combining serotonergic antidepressants with triptans
increases serotonin-syndrome risk as a focused pair.

Findings are advisory `SsriTriptanRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is always
**HIGH**.

## SSRI/SNRI panel

| Class | Agents |
|---|---|
| SSRI | sertraline, fluoxetine, paroxetine, citalopram, escitalopram, fluvoxamine |
| SNRI | venlafaxine, desvenlafaxine, duloxetine, levomilnacipran, milnacipran |

## Triptan partners

| Agents |
|---|
| sumatriptan, rizatriptan, eletriptan, zolmitriptan |
| naratriptan, almotriptan, frovatriptan |

Every unique SSRI/SNRI × triptan pair across separate medication entries yields
one finding. Matching is whole-token based, duplicates are de-duplicated by
canonical pair, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import SsriTriptanChecker

findings = SsriTriptanChecker().check(
    medications=[
        Medication(name="Sertraline 50 mg daily"),
        Medication(name="Sumatriptan 50 mg PRN"),
    ],
)
for finding in findings:
    print(
        finding.agent,
        finding.partner_agent,
        finding.antidepressant_class,
        finding.severity,
        finding.rationale,
    )
```

## Scope boundaries

This control targets the SSRI/SNRI × triptan serotonin-syndrome pair.
Broader multi-class serotonin screening belongs to `SerotoninSyndromeChecker`;
NSAID + SSRI/SNRI bleeding belongs to `NsaidSsriBleedChecker`. This control does
not replace serotonin-syndrome assessment or qualified clinical review, and it
never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.64](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Serotonin syndrome panel: `safety/serotonin_syndrome_checker.py`
- NSAID + SSRI/SNRI: `safety/nsaid_ssri_checker.py`
