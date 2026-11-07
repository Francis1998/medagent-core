# PercPeExclusionScorer Guide

![PercPeExclusionScorer](../../assets/perc_pe_exclusion_demo.gif)

Research-only PERC PE exclusion score. Never modifies medications.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `WellsPeProbabilityScorer` and `PaduaVteRiskScorer`.

## Usage

```python
from medagent.safety.perc_pe_exclusion_scorer import PercPeFactors, PercPeExclusionScorer

findings = PercPeExclusionScorer().check(PercPeFactors())
assert findings[0].rationale.startswith("RESEARCH USE ONLY")
print(findings[0].band, findings[0].score)
```
