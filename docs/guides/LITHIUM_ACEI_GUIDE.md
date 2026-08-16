# Lithium + ACE Inhibitor/ARB Toxicity Checker Guide

*medagent-core — Safety Control #76*

![Lithium ACEI/ARB checker flow](../../assets/lithium_acei_demo.gif)

## Overview

`LithiumAceiChecker` flags lithium, Lithobid, or Eskalith co-prescribed with a
supported ACE inhibitor or ARB. RAAS blockade may reduce renal lithium
clearance, increasing serum lithium concentrations and toxicity risk.

Findings are advisory `LithiumAceiRisk` records — **RESEARCH USE ONLY** — with
**HIGH** severity. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents |
|---|---|
| Lithium | lithium, lithobid, eskalith |
| ACE inhibitor | lisinopril, enalapril, ramipril, benazepril, quinapril, captopril, fosinopril, perindopril, trandolapril, moexipril |
| ARB | losartan, valsartan, olmesartan, candesartan, irbesartan, telmisartan, azilsartan |

Every unique lithium × ACEI/ARB pair across separate medication entries yields
one finding. Matching is whole-token based, canonical pairs are de-duplicated,
and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import LithiumAceiChecker

findings = LithiumAceiChecker().check(
    [Medication(name="Lithium 300 mg BID"), Medication(name="Lisinopril 10 mg")]
)
```

## Scope boundaries

This control is distinct from ACEI/ARB duplication, ACEI/ARB + trimethoprim,
and lithium + NSAID checks. It does not change therapy; obtain qualified
clinical review.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.76](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Lithium + NSAID: `safety/lithium_nsaid_checker.py`
