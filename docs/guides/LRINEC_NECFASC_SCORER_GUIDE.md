# LrinecNecfascScorer Guide

![LrinecNecfascScorer](../../assets/lrinec_necfasc_demo.gif)

Research-only advisory scorer. Closes the MDCalc / IDSA / EHR LRINEC necrotizing fasciitis score gap.

Optional later polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `CentorStrepPharyngitisScorer / SofaOrganFailureScorer`.

## Usage

```python
from medagent.safety.lrinec_necfasc_scorer import (
    LrinecNecfascScorer,
    LrinecNecfascFactors,
)

findings = LrinecNecfascScorer().check(LrinecNecfascFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No HTTP. See `SAFETY.md` #195.
