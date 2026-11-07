# EpworthSleepinessScorer Guide

![EpworthSleepinessScorer](../../assets/epworth_sleepiness_demo.gif)

Research-only advisory scorer. Gap vs MDCalc / AASM Epworth Sleepiness Scale screen. Distinct from `StopBangOsaScorer` / `MallampatiAirwayScorer`.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.epworth_sleepiness_scorer import (
    EpworthSleepinessFactors,
    EpworthSleepinessScorer,
)

findings = EpworthSleepinessScorer().check(EpworthSleepinessFactors())
print(findings[0].band)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. See `SAFETY.md` #233.
