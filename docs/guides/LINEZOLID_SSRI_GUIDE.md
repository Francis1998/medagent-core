# Linezolid + SSRI/SNRI Serotonin-Syndrome Checker Guide

*medagent-core — Safety Control #75*

![Linezolid SSRI checker flow](../../assets/linezolid_ssri_demo.gif)

## Overview

`LinezolidSsriChecker` flags linezolid co-prescribed with sertraline, fluoxetine,
paroxetine, citalopram, escitalopram, venlafaxine, or duloxetine. Linezolid has
reversible MAOI-like activity, and these combinations can precipitate
potentially life-threatening serotonin syndrome.

Findings are advisory `LinezolidSsriRisk` records — **RESEARCH USE ONLY** —
with **CRITICAL** severity. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents |
|---|---|
| Oxazolidinone / MAOI-like | linezolid |
| SSRI/SNRI | sertraline, fluoxetine, paroxetine, citalopram, escitalopram, venlafaxine, duloxetine |

Every unique linezolid × SSRI/SNRI pair across separate medication entries
yields one finding. Matching is whole-token based, canonical pairs are
de-duplicated, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import LinezolidSsriChecker

findings = LinezolidSsriChecker().check(
    [Medication(name="Linezolid 600 mg BID"), Medication(name="Sertraline 50 mg")]
)
```

## Scope boundaries

This focused control is distinct from tramadol + SSRI/SNRI and SSRI/SNRI +
triptan checks. It does not change therapy; obtain urgent qualified clinical
review.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.75](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Tramadol + SSRI/SNRI: `safety/tramadol_ssri_checker.py`
