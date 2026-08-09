# Amiodarone + Warfarin INR Interaction Checker Guide

*medagent-core — Safety Control #58*

![Amiodarone warfarin checker flow](../../assets/amio_warfarin_demo.gif)

## Overview

`AmioWarfarinChecker` flags **amiodarone-class agents** (amiodarone, cordarone,
pacerone) co-prescribed with **warfarin-class anticoagulants** (warfarin,
coumadin, jantoven). Amiodarone potentiates warfarin anticoagulation and can
raise INR, increasing bleeding risk.

Findings are advisory `AmioWarfarinRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is always
**HIGH**.

## Amiodarone-class panel

| Agent | Notes |
|---|---|
| amiodarone | antiarrhythmic; warfarin metabolism inhibitor |
| cordarone | amiodarone brand |
| pacerone | amiodarone brand |

## Warfarin-class partners

| Agent | Notes |
|---|---|
| warfarin | vitamin K antagonist |
| coumadin | warfarin brand |
| jantoven | warfarin brand |

Every amiodarone × warfarin pair yields one finding. Medication matching is
whole-token based.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import AmioWarfarinChecker

findings = AmioWarfarinChecker().check(
    medications=[
        Medication(name="Amiodarone 200 mg daily"),
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

## Reasoning stack notes

When this checker's findings are summarized by an upstream reasoning / routing
layer, prefer current frontier models for clinical prose:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## Suggested repo description / topics

**Description:** Research-only medical agent core with deterministic safety
checkers and modern LLM adapters (GPT-5.5, Claude Sonnet 4.6, Gemini 3.x,
Kimi K2).

**Topics:** `medical-ai`, `drug-safety`, `amiodarone`, `warfarin`, `inr`,
`agentic-ai`, `python`

## See also

- [SAFETY.md §3.58](../../SAFETY.md)
- [README safety controls table](../../README.md)
