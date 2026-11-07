# ImproveVteScorer Guide

![ImproveVteScorer](../../assets/improve_vte_scorer_demo.gif)

Research-only advisory score (Safety #260).
Gap vs MDCalc / IMPROVE VTE risk screen. Distinct from `PaduaVteRiskScorer` / `WellsPeProbabilityScorer`.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

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
