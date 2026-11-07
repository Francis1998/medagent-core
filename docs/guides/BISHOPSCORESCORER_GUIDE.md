# BishopScoreScorer Guide

![BishopScoreScorer demo](../../assets/bishop-score_demo.gif)

Research-only advisory scorer. Never modifies medications. Never network I/O.
Closes gaps vs MDCalc / ACOG Bishop score for induction readiness.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.bishop_score_scorer import BishopScoreFactors, BishopScoreScorer

findings = BishopScoreScorer().check(BishopScoreFactors())
assert "RESEARCH USE ONLY" in findings[0].rationale
```

## Safety

See `SAFETY.md` §3.221. Humans decide therapy.
