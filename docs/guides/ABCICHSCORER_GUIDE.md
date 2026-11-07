# AbcIchScorer Guide

![AbcIchScorer](../../assets/abc_ich_scorer_demo.gif)

Research-only advisory score (Safety #261).
Gap vs MDCalc / ABC ICH volume/severity screen. Distinct from `IchScoreScorer` / `HuntHessSahScorer`.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.abc_ich_scorer import (
    AbcIchFactors,
    AbcIchScorer,
)

findings = AbcIchScorer().check(AbcIchFactors())
assert findings[0].rationale
print(findings[0].band)
```

## Safety

RESEARCH USE ONLY. Advisory. Never modifies medications. No network I/O.
