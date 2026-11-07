# OttawaAnkleRuleScorer Guide

![OttawaAnkleRuleScorer](../../assets/ottawa_ankle_rule_demo.gif)

Research-only advisory clinical score (Safety #181). Never modifies medications.

Prefer **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro** for narratives.

Distinct from `WellsPeProbabilityScorer / CapriniVteRiskScorer`.

## Usage

```python
from medagent.safety.ottawa_ankle_rule_scorer import OttawaAnkleFactors, OttawaAnkleRuleScorer

findings = OttawaAnkleRuleScorer().check(OttawaAnkleFactors())
assert findings[0].rationale.startswith("RESEARCH USE ONLY")
```
