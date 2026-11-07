# LightCriteriaScorer Guide

![LightCriteriaScorer flow](../../assets/light-criteria_demo.gif)

Research-only advisory scorer (Safety #218). Never modifies medications.

Gap vs MDCalc / ATS Light criteria for pleural effusion. Distinct from `WellsPeProbabilityScorer / PsiPortPneumoniaScorer`.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.light_criteria_scorer import (
    LightCriteriaFactors,
    LightCriteriaScorer,
)

findings = LightCriteriaScorer().check(LightCriteriaFactors())
assert "RESEARCH USE ONLY" in findings[0].rationale
print(findings[0].band, findings[0].score)
```

## Safety

RESEARCH USE ONLY. See `SAFETY.md`.
