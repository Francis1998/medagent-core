# ACEI/ARB + Potassium Supplement Hyperkalemia Checker

*medagent-core — Safety Control #88*

![acei potassium checker flow](../../assets/acei_potassium_demo.gif)

## Overview

`AceiPotassiumChecker` flags ACE inhibitor or ARB therapy co-prescribed with potassium chloride or other potassium supplements. Concurrent exogenous potassium increases hyperkalemia risk.

Findings are advisory `AceiPotassiumRisk` records — **RESEARCH USE ONLY** — with **HIGH** severity. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents |
|---|---|
| ACEI | lisinopril, enalapril, ramipril, benazepril, captopril, fosinopril, perindopril, quinapril, trandolapril |
| ARB | losartan, valsartan, candesartan, irbesartan, olmesartan, telmisartan, azilsartan, eprosartan |
| Potassium supplement | potassium, kcl, klor-con, potassium-chloride |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import AceiPotassiumChecker

findings = AceiPotassiumChecker().check(
    [
        Medication(name="Lisinopril 10 mg"),
        Medication(name="Potassium Chloride 20 mEq"),
    ]
)
```

## Scope boundaries

This focused hyperkalemia control is distinct from ACEI/ARB + potassium-sparing diuretic screening (#3.60) and ACEI/ARB + trimethoprim / TMP-SMX screening (#3.63). Spironolactone, eplerenone, amiloride, triamterene, and trimethoprim partners remain out of scope here. The control does not replace medication reconciliation, patient-specific assessment, monitoring, or qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.88](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Generic interaction validation: `retrieval/drug_sources.py`
