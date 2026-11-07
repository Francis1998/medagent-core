# NexusCspineScorer Guide

![NexusCspineScorer flow](../../assets/nexus_cspine_demo.gif)

Research-only advisory scorer (Safety #210). Never modifies medications.

Gap vs MDCalc / ACEP / EHR NEXUS C-spine rule. Distinct from `CanadianCspineRuleScorer / OttawaAnkleRuleScorer`.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.nexus_cspine_scorer import (
    NexusCspineFactors,
    NexusCspineScorer,
)

findings = NexusCspineScorer().check(NexusCspineFactors())
assert "RESEARCH USE ONLY" in findings[0].rationale
print(findings[0].band, findings[0].score)
```

## Safety

RESEARCH USE ONLY. See `SAFETY.md`.
