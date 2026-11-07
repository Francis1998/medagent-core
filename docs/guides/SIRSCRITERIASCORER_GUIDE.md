# SirsCriteriaScorer Guide

![SirsCriteriaScorer demo](../../assets/sirs-criteria_demo.gif)

Research-only advisory scorer. Never modifies medications. Never network I/O.
Closes gaps vs MDCalc / SCCM SIRS criteria screen.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.sirs_criteria_scorer import SirsCriteriaFactors, SirsCriteriaScorer

findings = SirsCriteriaScorer().check(SirsCriteriaFactors())
assert "RESEARCH USE ONLY" in findings[0].rationale
```

## Safety

See `SAFETY.md` §3.225. Humans decide therapy.
