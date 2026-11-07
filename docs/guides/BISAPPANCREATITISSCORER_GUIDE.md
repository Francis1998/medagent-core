# BisapPancreatitisScorer Guide

![BisapPancreatitisScorer](../../assets/bisap_pancreatitis_demo.gif)

Research-only advisory scorer. Gap vs MDCalc / ACG BISAP pancreatitis severity screen. Distinct from `RansonPancreatitisScorer` / `MaddreyDiscriminantScorer`.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.bisap_pancreatitis_scorer import (
    BisapPancreatitisFactors,
    BisapPancreatitisScorer,
)

findings = BisapPancreatitisScorer().check(BisapPancreatitisFactors())
print(findings[0].band)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. See `SAFETY.md` #239.
