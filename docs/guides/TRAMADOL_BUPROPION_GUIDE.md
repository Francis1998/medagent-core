# Tramadol + Bupropion Seizure-Risk Checker

*medagent-core — Safety Control #83*

![tramadol bupropion checker flow](../../assets/tramadol_bupropion_demo.gif)

## Overview

`TramadolBupropionChecker` flags tramadol-class therapy co-prescribed with bupropion-class therapy. Both agents lower the seizure threshold, so concurrent use can compound seizure risk.

Findings are advisory `TramadolBupropionRisk` records — **RESEARCH USE ONLY** — with **HIGH** severity. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents |
|---|---|
| Tramadol | tramadol, ultram |
| Bupropion | bupropion, wellbutrin, zyban |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import TramadolBupropionChecker

findings = TramadolBupropionChecker().check(
    [
        Medication(name="Tramadol 50 mg"),
        Medication(name="Bupropion XL 150 mg"),
    ]
)
```

## Scope boundaries

This focused control is distinct from `TramadolSsriChecker`, which evaluates tramadol with SSRI/SNRI partners and includes serotonergic toxicity. The control does not replace medication reconciliation, patient-specific assessment, monitoring, or qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.83](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Tramadol + SSRI/SNRI: `safety/tramadol_ssri_checker.py`
