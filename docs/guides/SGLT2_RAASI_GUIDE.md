# SGLT2 + ACEI/ARB/ARNI Checker Guide

*medagent-core — Safety Control #72*

![SGLT2 RAASI checker flow](../../assets/sglt2_raasi_demo.gif)

## Overview

`Sglt2RaasiChecker` flags an SGLT2 inhibitor co-prescribed with an ACE inhibitor,
ARB, or ARNI. Concurrent SGLT2 inhibitor and RAAS blockade increases volume
depletion, hypotension, acute kidney injury, and hyperkalemia risk.

Findings are advisory `Sglt2RaasiRisk` records — **RESEARCH USE ONLY** — with
**HIGH** severity. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents |
|---|---|
| SGLT2 inhibitor | empagliflozin, dapagliflozin, canagliflozin, ertugliflozin |
| ACEI / ARB / ARNI | lisinopril, enalapril, ramipril, benazepril, quinapril, captopril, fosinopril, perindopril, trandolapril, moexipril, losartan, valsartan, olmesartan, candesartan, irbesartan, telmisartan, sacubitril, entresto |

Every unique SGLT2 × RAASI pair across separate medication entries yields one
finding. Matching is whole-token based, duplicates are de-duplicated by
canonical pair, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import Sglt2RaasiChecker

findings = Sglt2RaasiChecker().check(
    medications=[
        Medication(name="Empagliflozin 10 mg daily"),
        Medication(name="Lisinopril 10 mg daily"),
    ],
)
for finding in findings:
    print(finding.agent, finding.partner_agent, finding.severity)
```

## Scope boundaries

This control targets SGLT2 + RAASI volume-depletion and hyperkalemia risk. It is
distinct from SGLT2 + loop diuretic screening, ACEI/ARB duplication checks, and
ACEI + potassium-sparing hyperkalemia controls. It never changes therapy;
obtain qualified clinical review.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.72](../../SAFETY.md)
- [README safety controls table](../../README.md)
- SGLT2 + loop diuretic: `safety/sglt2_loop_checker.py`
