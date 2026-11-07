# GlasgowBlatchfordScorer Guide

![GlasgowBlatchfordScorer flow](../../assets/glasgow_blatchford_demo.gif)

Research-only advisory scorer (Safety #202). Never modifies medications.

Gap vs MDCalc / ACG / EHR Glasgow-Blatchford GI bleed score. Distinct from `RockallGiBleedScorer / Curb65PneumoniaScorer`.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.glasgow_blatchford_scorer import (
    GlasgowBlatchfordFactors,
    GlasgowBlatchfordScorer,
)

findings = GlasgowBlatchfordScorer().check(GlasgowBlatchfordFactors())
assert "RESEARCH USE ONLY" in findings[0].rationale
print(findings[0].band, findings[0].score)
```

## Safety

RESEARCH USE ONLY. See `SAFETY.md`.
