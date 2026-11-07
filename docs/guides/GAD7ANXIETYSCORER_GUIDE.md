# Gad7AnxietyScorer Guide

![Gad7AnxietyScorer](../../assets/gad7_anxiety_demo.gif)

Research-only advisory scorer. Gap vs MDCalc / USPSTF GAD-7 anxiety severity screen. Distinct from `Phq9DepressionScorer` / `EpworthSleepinessScorer`.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.gad7_anxiety_scorer import (
    Gad7AnxietyFactors,
    Gad7AnxietyScorer,
)

findings = Gad7AnxietyScorer().check(Gad7AnxietyFactors())
print(findings[0].band)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. See `SAFETY.md` #243.
