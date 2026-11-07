# MorseFallScorer Guide

![MorseFallScorer](../../assets/morse_fall_demo.gif)

Research-only advisory scorer. Gap vs MDCalc / AHRQ Morse Fall Scale screen. Distinct from `News2EarlyWarningScorer` / `PewsEarlyWarningScorer`.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.morse_fall_scorer import (
    MorseFallFactors,
    MorseFallScorer,
)

findings = MorseFallScorer().check(MorseFallFactors())
print(findings[0].band)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. See `SAFETY.md` #241.
