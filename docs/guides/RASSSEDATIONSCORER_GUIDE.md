# RassSedationScorer Guide

![RassSedationScorer](../../assets/rass_sedation_scorer_demo.gif)

Research-only advisory scorer. Gap vs MDCalc / SCCM Richmond Agitation-Sedation Scale (RASS) screen.
Distinct from `CamIcuDeliriumScorer` / `CiwaArWithdrawalScorer`. Safety #247.

Narrative polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.rass_sedation_scorer import RassSedationFactors, RassSedationScorer

findings = RassSedationScorer().check(RassSedationFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No network I/O.
