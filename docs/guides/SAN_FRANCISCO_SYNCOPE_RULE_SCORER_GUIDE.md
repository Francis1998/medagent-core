# SanFranciscoSyncopeRuleScorer Guide

![SanFranciscoSyncopeRuleScorer](../../assets/san_francisco_syncope_rule_demo.gif)

Research-only advisory scorer. Closes the MDCalc / ACEP / EHR San Francisco Syncope Rule gap.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `NihssStrokeScorer / FallRiskChecker`.

## Usage

```python
from medagent.safety.san_francisco_syncope_rule_scorer import (
    SanFranciscoSyncopeRuleScorer,
    SanFranciscoSyncopeFactors,
)

findings = SanFranciscoSyncopeRuleScorer().check(SanFranciscoSyncopeFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No HTTP. See `SAFETY.md` #190.
