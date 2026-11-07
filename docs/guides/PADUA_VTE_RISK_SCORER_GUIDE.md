# PaduaVteRiskScorer Guide

![PaduaVteRiskScorer](../../assets/padua_vte_risk_demo.gif)

Research-only advisory clinical score (Safety #183). Never modifies medications.

Prefer **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro** for narratives.

Distinct from `CapriniVteRiskScorer / WellsPeProbabilityScorer`.

## Usage

```python
from medagent.safety.padua_vte_risk_scorer import PaduaVteFactors, PaduaVteRiskScorer

findings = PaduaVteRiskScorer().check(PaduaVteFactors())
assert findings[0].rationale.startswith("RESEARCH USE ONLY")
```
