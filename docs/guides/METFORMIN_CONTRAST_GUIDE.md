# Metformin + Iodinated Contrast Media Lactic Acidosis Checker

*medagent-core — Safety Control #89*

![metformin contrast checker flow](../../assets/metformin_contrast_demo.gif)

## Overview

`MetforminContrastChecker` flags metformin therapy co-prescribed with iodinated contrast media used in imaging studies. Contrast can transiently impair renal function; when metformin clearance is reduced, the biguanide can accumulate and precipitate life-threatening lactic acidosis.

Findings are advisory `MetforminContrastRisk` records — **RESEARCH USE ONLY** — with **HIGH** severity. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents |
|---|---|
| Metformin | metformin, glucophage, fortamet, glumetza, riomet |
| Iodinated contrast media | contrast, contrast-media, iohexol, iodixanol, iopamidol |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import MetforminContrastChecker

findings = MetforminContrastChecker().check(
    [
        Medication(name="Metformin 500 mg"),
        Medication(name="Iohexol injection"),
    ]
)
```

## Scope boundaries

This focused peri-contrast control is distinct from general metformin renal-dose checking. It flags the co-prescription pattern itself; it does not evaluate eGFR thresholds, contrast volume, or hold/resume timing. The control does not replace medication reconciliation, patient-specific assessment, monitoring, or qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.89](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Generic interaction validation: `retrieval/drug_sources.py`
