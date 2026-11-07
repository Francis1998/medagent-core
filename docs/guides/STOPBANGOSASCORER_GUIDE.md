# StopBangOsaScorer Guide

![StopBangOsaScorer demo](../../assets/stop-bang-osa_demo.gif)

Research-only advisory scorer. Never modifies medications. Gap vs MDCalc / ASA STOP-BANG OSA screen.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `EpworthSleepiness / MallampatiAirwayScorer`.

## Usage

```python
from medagent.safety.stop_bang_osa_scorer import (
    StopBangOsaFactors,
    StopBangOsaScorer,
)

findings = StopBangOsaScorer().check(StopBangOsaFactors())
print(findings[0].band, findings[0].rationale)
```
