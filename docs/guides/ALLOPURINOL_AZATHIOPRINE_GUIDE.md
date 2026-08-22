# Allopurinol + Azathioprine / 6-MP Toxicity Checker

*medagent-core — Safety Control #86*

![allopurinol azathioprine checker flow](../../assets/allopurinol_azathioprine_demo.gif)

## Overview

`AllopurinolAzathioprineChecker` flags allopurinol-class therapy co-prescribed with azathioprine or mercaptopurine. Xanthine oxidase inhibition markedly increases thiopurine exposure and can cause severe myelosuppression.

Findings are advisory `AllopurinolAzathioprineRisk` records — **RESEARCH USE ONLY** — with **CRITICAL** severity. The checker is exported from `medagent.safety`.

## Medication panels

| Class | Agents |
|---|---|
| Allopurinol | allopurinol, zyloprim |
| Thiopurine | azathioprine, imuran, mercaptopurine, 6-mp, purinethol |

Every unique supported pair across separate medication entries yields one finding. Matching is whole-token/whole-alias based, canonical pairs are de-duplicated, and output ordering is deterministic.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import AllopurinolAzathioprineChecker

findings = AllopurinolAzathioprineChecker().check(
    [
        Medication(name="Allopurinol 300 mg"),
        Medication(name="Azathioprine 50 mg"),
    ]
)
```

## Scope boundaries

This contraindicated pair is a focused xanthine-oxidase / thiopurine safety control; it does not treat febuxostat or non-thiopurine immunosuppressants as in-scope partners. The control does not replace medication reconciliation, patient-specific assessment, monitoring, or qualified clinical review, and never changes therapy.

## Reasoning stack notes

When findings are summarized by an upstream reasoning/routing layer, prefer:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.86](../../SAFETY.md)
- [README safety controls table](../../README.md)
- Generic interaction validation: `retrieval/drug_sources.py`
