# Methotrexate + Penicillin Toxicity Checker

*medagent-core — Safety Control #84*

![mtx penicillin checker flow](../../assets/mtx_penicillin_demo.gif)

## Overview

`MtxPenicillinChecker` flags methotrexate-class therapy co-prescribed with penicillin-class antibiotic therapy. Penicillin-class antibiotics can reduce renal methotrexate clearance, increasing exposure and toxicity risk.

Findings are advisory `MtxPenicillinRisk` records — **RESEARCH USE ONLY** — with **HIGH** severity. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents |
|---|---|
| Methotrexate | methotrexate, mtx |
| Penicillin | penicillin, penicillin-v, pen-vk, amoxicillin, ampicillin |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import MtxPenicillinChecker

findings = MtxPenicillinChecker().check(
    [
        Medication(name="Methotrexate 15 mg weekly"),
        Medication(name="Amoxicillin 500 mg"),
    ]
)
```

## Scope boundaries

This focused control is distinct from `MtxNsaidChecker` and `MtxTmpsmxChecker`; those controls cover NSAID-related clearance effects and additive antifolate toxicity, respectively. The control does not replace medication reconciliation, patient-specific assessment, monitoring, or qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.84](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Methotrexate + NSAID: `safety/mtx_nsaid_checker.py`
- Methotrexate + TMP-SMX: `safety/mtx_tmpsmx_checker.py`
