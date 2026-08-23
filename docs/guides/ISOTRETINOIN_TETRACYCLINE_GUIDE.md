# Isotretinoin + Tetracycline-Class Pseudotumor Cerebri Checker

*medagent-core — Safety Control #90*

![isotretinoin tetracycline checker flow](../../assets/isotretinoin_tetracycline_demo.gif)

## Overview

`IsotretinoinTetracyclineChecker` flags isotretinoin (Accutane and related brand formulations) co-prescribed with tetracycline-class antibiotics (tetracycline, doxycycline, minocycline). Both agents are independently associated with idiopathic intracranial hypertension; co-prescription can precipitate pseudotumor cerebri with irreversible vision loss.

Findings are advisory `IsotretinoinTetracyclineRisk` records — **RESEARCH USE ONLY** — with **CRITICAL** severity. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents |
|---|---|
| Isotretinoin | isotretinoin, accutane, absorica, claravis, myorisan, zenatane |
| Tetracycline-class antibiotic | tetracycline, doxycycline, minocycline |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import IsotretinoinTetracyclineChecker

findings = IsotretinoinTetracyclineChecker().check(
    [
        Medication(name="Isotretinoin 40 mg"),
        Medication(name="Doxycycline 100 mg"),
    ]
)
```

## Scope boundaries

This is a targeted contraindication check for the isotretinoin + tetracycline-class combination itself. It does not evaluate other acne regimens, other retinoids, or other antibiotic classes. The control does not replace medication reconciliation, patient-specific assessment, monitoring, or qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.90](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Generic interaction validation: `retrieval/drug_sources.py`
