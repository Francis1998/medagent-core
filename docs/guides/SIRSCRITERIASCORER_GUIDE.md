# SirsCriteriaScorer Guide

![SirsCriteriaScorer demo](../../assets/sirs-criteria_demo.gif)

Research-only advisory scorer. Never modifies medications. Never network I/O.
Closes gaps vs MDCalc / SCCM SIRS criteria screen.

Optional narrative via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.sirs_criteria_scorer import SirsCriteriaFactors, SirsCriteriaScorer

findings = SirsCriteriaScorer().check(SirsCriteriaFactors())
assert "RESEARCH USE ONLY" in findings[0].rationale
```

## Safety

See `SAFETY.md` §3.225. Humans decide therapy.
