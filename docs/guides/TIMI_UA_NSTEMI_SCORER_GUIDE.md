# TimiUaNstemiScorer Guide

![TimiUaNstemiScorer](../../assets/timi_ua_nstemi_demo.gif)

Research-only advisory clinical score. Never modifies medications.
Closes MDCalc / ACC / EHR TIMI UA/NSTEMI gaps.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `PercPeExclusionScorer / WellsDvtProbabilityScorer`.

## Usage

```python
from medagent.safety.timi_ua_nstemi_scorer import (
    TimiUaNstemiScorer,
    TimiUaNstemiFactors,
)

findings = TimiUaNstemiScorer().check(TimiUaNstemiFactors())
print(findings[0].band, findings[0].score)
```
