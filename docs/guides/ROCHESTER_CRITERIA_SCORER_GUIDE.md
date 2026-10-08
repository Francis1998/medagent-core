# RochesterCriteriaScorer Guide

![RochesterCriteriaScorer flow](../../assets/rochester-criteria_demo.gif)

Research-only advisory scorer (Safety #217). Never modifies medications.

Gap vs MDCalc / AAP Rochester criteria for febrile infants. Distinct from `PecarnHeadTraumaScorer / CentorStrepPharyngitisScorer`.

Optional polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.rochester_criteria_scorer import (
    RochesterCriteriaFactors,
    RochesterCriteriaScorer,
)

findings = RochesterCriteriaScorer().check(RochesterCriteriaFactors())
assert "RESEARCH USE ONLY" in findings[0].rationale
print(findings[0].band, findings[0].score)
```

## Safety

RESEARCH USE ONLY. See `SAFETY.md`.
