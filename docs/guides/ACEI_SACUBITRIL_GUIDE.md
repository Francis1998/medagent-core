# ACE Inhibitor + Sacubitril/Entresto Checker Guide

*medagent-core — Safety Control #70*

![ACEI sacubitril checker flow](../../assets/acei_sacubitril_demo.gif)

## Overview

`AceiSacubitrilChecker` flags an ACE inhibitor overlapping with sacubitril or
Entresto. Concurrent ACE and neprilysin inhibition is contraindicated because
it substantially increases angioedema risk. A minimum **36-hour washout** is
required between an ACE inhibitor and sacubitril-containing therapy.

Findings are advisory `AceiSacubitrilRisk` records — **RESEARCH USE ONLY** —
with **CRITICAL** severity. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents |
|---|---|
| ACE inhibitor | lisinopril, enalapril, ramipril, benazepril, quinapril, captopril, fosinopril, perindopril, trandolapril, moexipril |
| Sacubitril-containing therapy | sacubitril, entresto |

Every unique ACE inhibitor × sacubitril/Entresto pair across separate
medication entries yields one finding. Matching is whole-token based,
duplicates are de-duplicated by canonical pair, and output ordering is
deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import AceiSacubitrilChecker

findings = AceiSacubitrilChecker().check(
    medications=[
        Medication(name="Lisinopril 10 mg daily"),
        Medication(name="Entresto 24/26 mg BID"),
    ],
)
for finding in findings:
    print(finding.agent, finding.partner_agent, finding.severity)
```

## Scope boundaries

This focused control detects the contraindicated ACE inhibitor +
sacubitril/Entresto overlap and calls out the 36-hour washout. It is distinct
from broad ACEI/ARB/ARNI duplication screening. It does not establish actual
administration timing and never changes therapy; obtain urgent qualified
clinical review.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.70](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Broad RAAS duplication: `safety/acei_arb_duplication_checker.py`
