# ImproveVteScorer Guide

![ImproveVteScorer](../../assets/improve_vte_scorer_demo.gif)

Research-only advisory score (Safety #260).
Gap vs MDCalc / IMPROVE VTE risk screen. Distinct from `PaduaVteRiskScorer` / `WellsPeProbabilityScorer`.

Optional narrative via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.improve_vte_scorer import (
    ImproveVteFactors,
    ImproveVteScorer,
)

findings = ImproveVteScorer().check(ImproveVteFactors())
assert findings[0].rationale
print(findings[0].band)
```

## Safety

RESEARCH USE ONLY. Advisory. Never modifies medications. No network I/O.
