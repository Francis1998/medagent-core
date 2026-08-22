# Codeine + CYP2D6 Inhibitor Checker

*medagent-core — Safety Control #87*

![codeine cyp2d6 checker flow](../../assets/codeine_cyp2d6_demo.gif)

## Overview

`CodeineCyp2d6Checker` flags codeine-class therapy co-prescribed with strong CYP2D6 inhibitors. Codeine requires CYP2D6 bioactivation to morphine; inhibitors can reduce analgesia and alter exposure.

Findings are advisory `CodeineCyp2d6Risk` records — **RESEARCH USE ONLY** — with **HIGH** severity. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents |
|---|---|
| Codeine | codeine, tylenol-with-codeine |
| Strong CYP2D6 inhibitor | fluoxetine, paroxetine, bupropion, quinidine, terbinafine |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import CodeineCyp2d6Checker

findings = CodeineCyp2d6Checker().check(
    [
        Medication(name="Codeine 30 mg"),
        Medication(name="Fluoxetine 20 mg"),
    ]
)
```

## Scope boundaries

This focused pharmacokinetic control is distinct from opioid + benzodiazepine, opioid MED, and tramadol interaction checkers. Weak or moderate CYP2D6 inhibitors and non-codeine opioids remain out of scope. The control does not replace medication reconciliation, patient-specific assessment, monitoring, or qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.87](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Generic interaction validation: `retrieval/drug_sources.py`
