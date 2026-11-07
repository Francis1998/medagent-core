# MewsScorer Guide

![MewsScorer flow](../../assets/mews_demo.gif)

Research-only advisory scorer (Safety #211). Never modifies medications.

Gap vs MDCalc / NICE / EHR MEWS. Distinct from `News2EarlyWarningScorer / VitalsTriageChecker`.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.mews_scorer import (
    MewsFactors,
    MewsScorer,
)

findings = MewsScorer().check(MewsFactors())
assert "RESEARCH USE ONLY" in findings[0].rationale
print(findings[0].band, findings[0].score)
```

## Safety

RESEARCH USE ONLY. See `SAFETY.md`.
