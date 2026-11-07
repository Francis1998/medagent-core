# CanadianCspineRuleScorer Guide

![CanadianCspineRuleScorer](../../assets/canadian_cspine_rule_demo.gif)

Research-only advisory clinical score. Never modifies medications.
Closes MDCalc / CAEP / EHR Canadian C-spine rule gaps.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `OttawaAnkleRuleScorer / FallRiskChecker`.

## Usage

```python
from medagent.safety.canadian_cspine_rule_scorer import (
    CanadianCspineRuleScorer,
    CanadianCspineFactors,
)

findings = CanadianCspineRuleScorer().check(CanadianCspineFactors())
print(findings[0].band, findings[0].score)
```
