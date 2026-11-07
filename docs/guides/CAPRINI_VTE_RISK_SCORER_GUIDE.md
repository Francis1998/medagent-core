# CapriniVteRiskScorer Guide

![CapriniVteRiskScorer](../../assets/caprini_vte_risk_demo.gif)

Research-only advisory clinical score (Safety #180). Never modifies medications.

Prefer **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro** for narratives.

Distinct from `WellsPeProbabilityScorer / HasBledBleedRiskScorer`.

## Usage

```python
from medagent.safety.caprini_vte_risk_scorer import CapriniVteFactors, CapriniVteRiskScorer

findings = CapriniVteRiskScorer().check(CapriniVteFactors())
assert findings[0].rationale.startswith("RESEARCH USE ONLY")
```
