# BishopScoreScorer Guide

![BishopScoreScorer demo](../../assets/bishop-score_demo.gif)

Research-only advisory scorer. Never modifies medications. Never network I/O.
Closes gaps vs MDCalc / ACOG Bishop score for induction readiness.

Optional narrative via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.bishop_score_scorer import BishopScoreFactors, BishopScoreScorer

findings = BishopScoreScorer().check(BishopScoreFactors())
assert "RESEARCH USE ONLY" in findings[0].rationale
```

## Safety

See `SAFETY.md` §3.221. Humans decide therapy.
