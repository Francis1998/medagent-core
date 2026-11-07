# Abcd2TiaRiskScorer Guide

![Abcd2TiaRiskScorer](../../assets/abcd2_tia_risk_demo.gif)

Research-only advisory scorer. Closes the MDCalc / AHA / EHR ABCD2 TIA risk gap.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `NihssStrokeScorer / Cha2ds2VascStrokeRiskScorer`.

## Usage

```python
from medagent.safety.abcd2_tia_risk_scorer import (
    Abcd2TiaRiskScorer,
    Abcd2TiaFactors,
)

findings = Abcd2TiaRiskScorer().check(Abcd2TiaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No HTTP. See `SAFETY.md` #191.
