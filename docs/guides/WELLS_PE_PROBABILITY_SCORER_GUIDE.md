# WellsPeProbabilityScorer Guide

![WellsPeProbabilityScorer](../../assets/wells_pe_probability_demo.gif)

Research-only advisory clinical score. Never modifies medications.

Prefer **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro** for narratives.

Distinct from `HasBledBleedRiskScorer / Cha2ds2VascStrokeRiskScorer`.

## Usage

```python
from medagent.safety.wells_pe_probability_scorer import WellsPeFactors, WellsPeProbabilityScorer

findings = WellsPeProbabilityScorer().check(WellsPeFactors())
assert findings[0].rationale.startswith("RESEARCH USE ONLY")
```
