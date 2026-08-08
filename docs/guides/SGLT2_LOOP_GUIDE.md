# SGLT2 + Loop Diuretic Volume Depletion Checker Guide

*medagent-core — Safety Control #53*

![SGLT2 loop checker flow](../../assets/sglt2_loop_demo.gif)

## Overview

`Sglt2LoopChecker` flags **SGLT2 inhibitors** (empagliflozin, dapagliflozin,
canagliflozin, ertugliflozin) co-prescribed with **loop diuretics**
(furosemide, bumetanide, torsemide, ethacrynic acid). Concurrent therapy
increases volume depletion, hypotension, and acute kidney injury risk. This
check complements the triple-whammy renal panel and generic drug-drug
interaction screening.

Findings are advisory `Sglt2LoopRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is always
**HIGH**.

## SGLT2 inhibitor panel

| Agent | Notes |
|---|---|
| empagliflozin | SGLT2 inhibitor |
| dapagliflozin | SGLT2 inhibitor |
| canagliflozin | SGLT2 inhibitor |
| ertugliflozin | SGLT2 inhibitor |

## Loop diuretic partners

| Agent | Notes |
|---|---|
| furosemide | loop diuretic |
| bumetanide | loop diuretic |
| torsemide | loop diuretic |
| ethacrynic | ethacrynic acid (loop diuretic) |

Every SGLT2 × loop pair yields one finding. Medication matching is
whole-token based.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import Sglt2LoopChecker

findings = Sglt2LoopChecker().check(
    medications=[
        Medication(name="Empagliflozin 10 mg daily"),
        Medication(name="Furosemide 40 mg daily"),
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

**Topics:** `medical-ai`, `drug-safety`, `sglt2`, `agentic-ai`, `python`

## See also

- [SAFETY.md §3.53](../../SAFETY.md)
- [README safety controls table](../../README.md)
