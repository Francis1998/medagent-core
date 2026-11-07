# KillipClassScorer Guide

![KillipClassScorer flow](../../assets/killip_class_demo.gif)

Research-only advisory scorer (Safety #206). Never modifies medications.

Gap vs MDCalc / ACC / EHR Killip classification. Distinct from `TimiUaNstemiScorer / HeartScoreAcsScorer`.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.killip_class_scorer import (
    KillipClassFactors,
    KillipClassScorer,
)

findings = KillipClassScorer().check(KillipClassFactors())
assert "RESEARCH USE ONLY" in findings[0].rationale
print(findings[0].band, findings[0].score)
```

## Safety

RESEARCH USE ONLY. See `SAFETY.md`.
