# PewsEarlyWarningScorer Guide

![PewsEarlyWarningScorer demo](../../assets/pews-early-warning_demo.gif)

Research-only advisory scorer. Never modifies medications. Never network I/O.
Closes gaps vs MDCalc / RCN PEWS pediatric early warning score.

Optional narrative via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.pews_early_warning_scorer import (
    PewsEarlyWarningFactors,
    PewsEarlyWarningScorer,
)

findings = PewsEarlyWarningScorer().check(PewsEarlyWarningFactors())
assert "RESEARCH USE ONLY" in findings[0].rationale
```

## Safety

See `SAFETY.md` §3.223. Humans decide therapy.
