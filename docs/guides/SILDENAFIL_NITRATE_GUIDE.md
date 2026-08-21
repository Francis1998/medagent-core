# Sildenafil + Nitrate Critical Hypotension Checker

*medagent-core — Safety Control #85*

![sildenafil nitrate checker flow](../../assets/sildenafil_nitrate_demo.gif)

## Overview

`SildenafilNitrateChecker` flags sildenafil-class therapy co-prescribed with nitrate therapy. PDE-5 inhibition amplifies nitrate-mediated cyclic-GMP vasodilation and can cause profound, life-threatening hypotension.

Findings are advisory `SildenafilNitrateRisk` records — **RESEARCH USE ONLY** — with **CRITICAL** severity. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents |
|---|---|
| Sildenafil | sildenafil, viagra, revatio |
| Nitrate | nitroglycerin, isosorbide, imdur, monoket |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import SildenafilNitrateChecker

findings = SildenafilNitrateChecker().check(
    [
        Medication(name="Sildenafil 50 mg"),
        Medication(name="Nitroglycerin 0.4 mg SL"),
    ]
)
```

## Scope boundaries

This contraindicated pair is a focused hemodynamic safety control; it does not treat non-nitrate antianginals or antihypertensives as nitrate partners. The control does not replace medication reconciliation, patient-specific assessment, monitoring, or qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.85](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Generic interaction validation: `retrieval/drug_sources.py`
