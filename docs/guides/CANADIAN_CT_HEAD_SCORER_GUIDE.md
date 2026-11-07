# CanadianCtHeadScorer Guide

![CanadianCtHeadScorer flow](../../assets/canadian_ct_head_demo.gif)

Research-only advisory scorer (Safety #216). Never modifies medications.

Gap vs MDCalc / ACEP Canadian CT Head Rule. Distinct from `PecarnHeadTraumaScorer / NexusCspineScorer`.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.canadian_ct_head_scorer import (
    CanadianCtHeadFactors,
    CanadianCtHeadScorer,
)

findings = CanadianCtHeadScorer().check(CanadianCtHeadFactors())
assert "RESEARCH USE ONLY" in findings[0].rationale
print(findings[0].band, findings[0].score)
```

## Safety

RESEARCH USE ONLY. See `SAFETY.md`.
