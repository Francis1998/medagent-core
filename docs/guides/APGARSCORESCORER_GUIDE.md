# ApgarScoreScorer Guide

![ApgarScoreScorer demo](../../assets/apgar-score_demo.gif)

Research-only advisory scorer. Never modifies medications. Never network I/O.
Closes gaps vs MDCalc / AAP Apgar newborn score.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.apgar_score_scorer import ApgarScoreFactors, ApgarScoreScorer

findings = ApgarScoreScorer().check(ApgarScoreFactors())
assert "RESEARCH USE ONLY" in findings[0].rationale
```

## Safety

See `SAFETY.md` §3.222. Humans decide therapy.
