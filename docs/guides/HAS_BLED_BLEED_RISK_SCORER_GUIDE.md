# HAS-BLED Bleed Risk Scorer Guide

![HAS-BLED bleed risk scorer](../../assets/has_bled_bleed_risk_demo.gif)

Advisory HAS-BLED totals from clinical factors (Safety **#169**). RESEARCH USE
ONLY. Never modifies medications. Closes the MDCalc / UpToDate / EHR HAS-BLED
calculator gap for offline agent pipelines.

Optional later polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

Distinct from `AnticoagBleedingChecker` and `AnticoagBleedStackPanel`.

## Usage

```python
from medagent.safety.has_bled_bleed_risk_scorer import (
    HasBledBleedRiskScorer,
    HasBledFactors,
)

findings = HasBledBleedRiskScorer().check(
    HasBledFactors(hypertension=True, elderly=True, drugs=True)
)
assert findings[0].score == 3
assert findings[0].band == "high"
```
