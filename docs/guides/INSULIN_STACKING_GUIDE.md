# Insulin Stacking Checker Guide

*medagent-core — Safety Control #45*

![Insulin stacking checker flow](../../assets/insulin_stacking_demo.gif)

## Overview

`InsulinStackingChecker` flags **overlapping rapid-acting insulin boluses**
when `hours_since_last_bolus` is below three hours without meal or correction
context, and **concurrent premix plus bolus insulin** regimens that create
cumulative rapid-acting exposure.

Findings are advisory `InsulinStackingRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`.

## Finding kinds

| Kind | Trigger | Severity |
|---|---|---|
| `rapid_bolus_stacking` | Bolus &lt; 3 h ago without meal/correction context | HIGH |
| `premix_plus_bolus` | Concurrent premix and rapid-acting bolus insulin | CRITICAL |

## Insulin panels

| Role | Agents |
|---|---|
| rapid-acting bolus | lispro, aspart, glulisine |
| premix markers | protamine, mix, 70/30, 75/25, 50/50 |

Medication matching is whole-token based.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import InsulinStackingChecker

findings = InsulinStackingChecker().check(
    medications=[
        Medication(name="Humalog Mix 75/25"),
        Medication(name="Insulin lispro sliding scale"),
    ],
    hours_since_last_bolus=2.0,
    meal_context=False,
    correction_context=False,
)
for finding in findings:
    print(
        finding.agent,
        finding.finding_kind,
        finding.hours_since_last_bolus,
        finding.partner_agent,
        finding.severity,
        finding.rationale,
    )
```

## Reasoning stack notes

When this checker's findings are summarized by an upstream reasoning / routing
layer, prefer current frontier models for clinical prose:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.45](../../SAFETY.md)
- [README safety controls table](../../README.md)
