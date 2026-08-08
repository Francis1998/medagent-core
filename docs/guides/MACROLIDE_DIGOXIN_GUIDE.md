# Macrolide + Digoxin P-gp Checker Guide

*medagent-core — Safety Control #54*

![Macrolide digoxin checker flow](../../assets/macrolide_digoxin_demo.gif)

## Overview

`MacrolideDigoxinChecker` flags **digoxin / lanoxin** co-prescribed with
**clarithromycin or erythromycin** — macrolides that inhibit P-glycoprotein
(P-gp) and can raise digoxin serum concentrations. **Azithromycin is excluded**
as a weaker P-gp inhibitor. This check complements digoxin + amiodarone level
monitoring and digoxin toxicity electrolyte screening.

Findings are advisory `MacrolideDigoxinRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is always
**HIGH**.

## Digoxin panel

| Agent | Notes |
|---|---|
| digoxin | cardiac glycoside |
| lanoxin | digoxin brand |

## P-gp-inhibiting macrolide partners

| Agent | Notes |
|---|---|
| clarithromycin | strong P-gp inhibitor |
| erythromycin | P-gp inhibitor |

**Not included:** azithromycin (weaker P-gp inhibition).

Every digoxin × macrolide pair yields one finding. Medication matching is
whole-token based.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import MacrolideDigoxinChecker

findings = MacrolideDigoxinChecker().check(
    medications=[
        Medication(name="Digoxin 0.125 mg daily"),
        Medication(name="Clarithromycin 500 mg BID"),
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

- [SAFETY.md §3.54](../../SAFETY.md)
- [README safety controls table](../../README.md)
