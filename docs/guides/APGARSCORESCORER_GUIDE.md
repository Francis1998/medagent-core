# ApgarScoreScorer Guide

![ApgarScoreScorer demo](../../assets/apgar-score_demo.gif)

Research-only advisory scorer. Never modifies medications. Never network I/O.
Closes gaps vs MDCalc / AAP Apgar newborn score.

Optional narrative via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.apgar_score_scorer import ApgarScoreFactors, ApgarScoreScorer

findings = ApgarScoreScorer().check(ApgarScoreFactors())
assert "RESEARCH USE ONLY" in findings[0].rationale
```

## Safety

See `SAFETY.md` §3.222. Humans decide therapy.
