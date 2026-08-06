# Warfarin + NSAID Bleeding Intensifier Checker Guide

*medagent-core — Safety Control #49*

![Warfarin NSAID checker flow](../../assets/warfarin_nsaid_demo.gif)

## Overview

`WarfarinNsaidChecker` flags **warfarin / coumadin / jantoven** co-prescribed
with an **NSAID bleed intensifier** (ibuprofen, naproxen, diclofenac,
ketorolac, meloxicam, or aspirin). Concurrent warfarin-class anticoagulation
with an NSAID increases major bleeding risk via GI mucosal injury and platelet
dysfunction. This check complements the broader anticoagulation bleeding-risk
panel and generic drug-drug interaction flagging.

Findings are advisory `WarfarinNsaidRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is **HIGH** for
typical NSAIDs and **CRITICAL** for aspirin or ketorolac.

## Warfarin-class panel

| Agent | Notes |
|---|---|
| warfarin | vitamin K antagonist |
| coumadin | warfarin brand |
| jantoven | warfarin brand |

## NSAID partners

| Agent | Severity |
|---|---|
| ibuprofen | HIGH |
| naproxen | HIGH |
| diclofenac | HIGH |
| meloxicam | HIGH |
| ketorolac | CRITICAL |
| aspirin | CRITICAL |

Every warfarin × NSAID pair yields one finding. Medication matching is
whole-token based.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import WarfarinNsaidChecker

findings = WarfarinNsaidChecker().check(
    medications=[
        Medication(name="Warfarin 5 mg daily"),
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

**Topics:** `medical-ai`, `drug-safety`, `warfarin`, `agentic-ai`, `python`

## See also

- [SAFETY.md §3.49](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Broader anticoagulation bleeding risk: `safety/anticoag_bleeding_checker.py`
