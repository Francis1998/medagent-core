# WellsDvtProbabilityScorer Guide

![WellsDvtProbabilityScorer](../../assets/wells_dvt_probability_demo.gif)

Research-only Wells DVT probability score. Never modifies medications.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `WellsPeProbabilityScorer` and `CapriniVteRiskScorer`.

## Usage

```python
from medagent.safety.wells_dvt_probability_scorer import (
    WellsDvtFactors,
    WellsDvtProbabilityScorer,
)

findings = WellsDvtProbabilityScorer().check(WellsDvtFactors(active_cancer=1))
assert findings[0].rationale.startswith("RESEARCH USE ONLY")
print(findings[0].band, findings[0].score)
```
