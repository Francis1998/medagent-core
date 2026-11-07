# AspectsStrokeScorer Guide

![AspectsStrokeScorer](../../assets/aspects_stroke_scorer_demo.gif)

Research-only advisory score (Safety #258).
Gap vs MDCalc / ASPECTS early ischemic change screen. Distinct from `NihssStrokeScorer` / `CanadianCtHeadScorer`.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.aspects_stroke_scorer import (
    AspectsStrokeFactors,
    AspectsStrokeScorer,
)

findings = AspectsStrokeScorer().check(AspectsStrokeFactors())
assert findings[0].rationale
print(findings[0].band)
```

## Safety

RESEARCH USE ONLY. Advisory. Never modifies medications. No network I/O.
