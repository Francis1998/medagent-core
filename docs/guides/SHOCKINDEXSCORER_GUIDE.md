# ShockIndexScorer Guide

![ShockIndexScorer](../../assets/shock_index_demo.gif)

Research-only advisory scorer. Gap vs MDCalc / AHA Shock Index screen. Distinct from `QsofaSepsisScreenScorer` / `PhoenixSepsisCriteriaScorer`.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.shock_index_scorer import (
    ShockIndexFactors,
    ShockIndexScorer,
)

findings = ShockIndexScorer().check(ShockIndexFactors())
print(findings[0].band)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. See `SAFETY.md` #235.
