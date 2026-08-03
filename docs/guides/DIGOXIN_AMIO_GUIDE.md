# Digoxin + Amiodarone Level Monitoring Checker Guide

*medagent-core — Safety Control #48*

![Digoxin amiodarone checker flow](../../assets/digoxin_amio_demo.gif)

## Overview

`DigoxinAmioChecker` flags **digoxin / lanoxin** co-prescribed with
**amiodarone / cordarone** — a combination that inhibits digoxin clearance and
can approximately double digoxin serum concentrations. Findings recommend
digoxin dose review and serum digoxin level monitoring. This check complements
digoxin toxicity electrolyte screening and generic drug-drug interaction
flagging.

Findings are advisory `DigoxinAmioRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is always
**HIGH**.

## Digoxin panel

| Agent | Notes |
|---|---|
| digoxin | cardiac glycoside |
| lanoxin | digoxin brand |

## Amiodarone partners

| Agent | Notes |
|---|---|
| amiodarone | class III antiarrhythmic |
| cordarone | amiodarone brand |

Every digoxin × amiodarone pair yields one finding. Medication matching is
whole-token based.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import DigoxinAmioChecker

findings = DigoxinAmioChecker().check(
    medications=[
        Medication(name="Digoxin 0.125 mg daily"),
        Medication(name="Amiodarone 200 mg daily"),
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

**Topics:** `medical-ai`, `drug-safety`, `digoxin`, `agentic-ai`, `python`

## See also

- [SAFETY.md §3.48](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Digoxin toxicity electrolyte checking: `safety/digoxin_toxicity_checker.py`
