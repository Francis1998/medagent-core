# Clozapine ANC Monitoring Checker Guide

*medagent-core — Safety Control #52*

![Clozapine ANC checker flow](../../assets/clozapine_anc_demo.gif)

## Overview

`ClozapineAncChecker` flags **clozapine / Clozaril / FazaClo** therapy and
emits an **absolute neutrophil count (ANC) / agranulocytosis monitoring**
reminder. Clozapine carries a boxed warning for severe neutropenia and
requires scheduled ANC surveillance. This check complements generic
boxed-warning panels and drug-drug interaction screening.

Findings are advisory `ClozapineAncRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is always
**CRITICAL**. A finding is emitted whenever a clozapine-class agent is
present (monitoring reminder style).

## Clozapine-class panel

| Agent | Notes |
|---|---|
| clozapine | atypical antipsychotic; agranulocytosis risk |
| clozaril | clozapine brand |
| fazaclo | ODT clozapine brand |

Medication matching is whole-token based.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import ClozapineAncChecker

findings = ClozapineAncChecker().check(
    medications=[
        Medication(name="Clozapine 200 mg BID"),
    ],
)
for finding in findings:
    print(
        finding.agent,
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

**Topics:** `medical-ai`, `drug-safety`, `clozapine`, `agentic-ai`, `python`

## See also

- [SAFETY.md §3.52](../../SAFETY.md)
- [README safety controls table](../../README.md)
