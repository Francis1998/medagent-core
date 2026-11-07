# BradenPressureScorer Guide

![BradenPressureScorer](../../assets/braden_pressure_demo.gif)

Research-only advisory scorer. Gap vs MDCalc / NPUAP Braden pressure-injury risk screen. Distinct from `News2EarlyWarningScorer` / `SofaOrganFailureScorer`.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.braden_pressure_scorer import (
    BradenPressureFactors,
    BradenPressureScorer,
)

findings = BradenPressureScorer().check(BradenPressureFactors())
print(findings[0].band)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. See `SAFETY.md` #242.
