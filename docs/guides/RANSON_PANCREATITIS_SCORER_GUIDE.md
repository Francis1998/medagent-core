# RansonPancreatitisScorer Guide

![RansonPancreatitisScorer](../../assets/ranson_pancreatitis_demo.gif)

Research-only advisory scorer. Closes the MDCalc / ACG / EHR Ranson pancreatitis criteria gap.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `AlvaradoAppendicitisScorer / SofaOrganFailureScorer`.

## Usage

```python
from medagent.safety.ranson_pancreatitis_scorer import (
    RansonPancreatitisScorer,
    RansonPancreatitisFactors,
)

findings = RansonPancreatitisScorer().check(RansonPancreatitisFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No HTTP. See `SAFETY.md` #193.
