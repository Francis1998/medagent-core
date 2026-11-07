# PewsEarlyWarningScorer Guide

![PewsEarlyWarningScorer demo](../../assets/pews-early-warning_demo.gif)

Research-only advisory scorer. Never modifies medications. Never network I/O.
Closes gaps vs MDCalc / RCN PEWS pediatric early warning score.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

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
