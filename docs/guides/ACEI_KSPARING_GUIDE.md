# ACEI/ARB + Potassium-Sparing Hyperkalemia Checker Guide

*medagent-core — Safety Control #60*

![ACEI potassium-sparing checker flow](../../assets/acei_ksparing_demo.gif)

## Overview

`AceiKsparingChecker` flags an ACE inhibitor or angiotensin receptor blocker
(ARB) co-prescribed with spironolactone, eplerenone, amiloride, or triamterene.
Combining these therapies can increase hyperkalemia and renal-function risk.

Findings are advisory `AceiKsparingRisk` records — **RESEARCH USE ONLY** — and
the checker is exported from `medagent.safety`. Severity is always **HIGH**.

## ACEI/ARB panel

| Class | Agents |
|---|---|
| ACEI | lisinopril, enalapril, ramipril, benazepril, captopril, fosinopril, perindopril, quinapril, trandolapril |
| ARB | losartan, valsartan, candesartan, irbesartan, olmesartan, telmisartan, azilsartan, eprosartan |

## Potassium-sparing partners

| Agent | Class |
|---|---|
| spironolactone | mineralocorticoid receptor antagonist |
| eplerenone | mineralocorticoid receptor antagonist |
| amiloride | epithelial sodium-channel blocker |
| triamterene | epithelial sodium-channel blocker |

Every unique ACEI/ARB × potassium-sparing pair across separate medication
entries yields one finding. Matching is whole-token based, duplicates are
de-duplicated by canonical pair, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import AceiKsparingChecker

findings = AceiKsparingChecker().check(
    medications=[
        Medication(name="Lisinopril 20 mg daily"),
        Medication(name="Spironolactone 25 mg daily"),
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

This control requires one ACEI/ARB and one potassium-sparing agent. ACEI + ARB
dual blockade without a potassium-sparing partner belongs to
`AceiArbDuplicationChecker` and does not trigger this checker. This control
does not replace potassium/renal testing or qualified clinical review, and it
never changes therapy or monitoring plans.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.60](../../SAFETY.md)
- [README safety controls table](../../README.md)
- ACEI/ARB/ARNI duplication: `safety/acei_arb_duplication_checker.py`
