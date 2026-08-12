# ACEI/ARB + Trimethoprim / TMP-SMX Hyperkalemia Checker Guide

*medagent-core — Safety Control #63*

![ACEI trimethoprim checker flow](../../assets/acei_trimethoprim_demo.gif)

## Overview

`AceiTrimethoprimChecker` flags an ACE inhibitor or ARB co-prescribed with
trimethoprim or a TMP-SMX product. ACEI/ARB therapy reduces aldosterone activity
while trimethoprim blocks epithelial sodium channels in a potassium-sparing
manner, increasing hyperkalemia risk.

Findings are advisory `AceiTrimethoprimRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is **HIGH** for
trimethoprim and **CRITICAL** for TMP-SMX brand/generic products.

## ACEI/ARB panel

| Class | Agents |
|---|---|
| ACEI | lisinopril, enalapril, ramipril, benazepril, captopril, fosinopril, perindopril, quinapril, trandolapril |
| ARB | losartan, valsartan, candesartan, irbesartan, olmesartan, telmisartan, azilsartan, eprosartan |

## Trimethoprim / TMP-SMX partners

| Agents | Severity |
|---|---|
| trimethoprim | HIGH |
| bactrim, septra, cotrimoxazole | CRITICAL |

Every unique ACEI/ARB × trimethoprim pair across separate medication entries yields
one finding. Matching is whole-token based, duplicates are de-duplicated by
canonical pair, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import AceiTrimethoprimChecker

findings = AceiTrimethoprimChecker().check(
    medications=[
        Medication(name="Lisinopril 10 mg daily"),
        Medication(name="Trimethoprim 100 mg BID"),
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

## Scope boundaries

This control targets ACEI/ARB × trimethoprim / TMP-SMX hyperkalemia risk.
ACEI/ARB + potassium-sparing agents belong to `AceiKsparingChecker`; methotrexate +
TMP-SMX belongs to `MtxTmpsmxChecker`. This control does not replace potassium
monitoring or qualified clinical review, and it never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.63](../../SAFETY.md)
- [README safety controls table](../../README.md)
- ACEI/ARB + potassium-sparing: `safety/acei_ksparing_checker.py`
- Methotrexate + TMP-SMX: `safety/mtx_tmpsmx_checker.py`
