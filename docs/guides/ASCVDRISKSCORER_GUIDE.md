# AscvdRiskScorer Guide

![AscvdRiskScorer](../../assets/ascvd_risk_scorer_demo.gif)

Research-only advisory scorer. Gap vs MDCalc / ACC-AHA ASCVD 10-year risk screen.
Distinct from `HeartScoreAcsScorer` / `GraceAcsScorer`. Safety #244.

Narrative polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.ascvd_risk_scorer import AscvdRiskFactors, AscvdRiskScorer

findings = AscvdRiskScorer().check(AscvdRiskFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No network I/O.
