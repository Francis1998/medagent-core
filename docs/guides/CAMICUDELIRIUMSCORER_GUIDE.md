# CamIcuDeliriumScorer Guide

![CamIcuDeliriumScorer](../../assets/cam_icu_delirium_scorer_demo.gif)

Research-only advisory scorer. Gap vs MDCalc / SCCM CAM-ICU delirium screen.
Distinct from `GcsNeurologicStatusScorer` / `CiwaArWithdrawalScorer`. Safety #245.

Narrative polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.cam_icu_delirium_scorer import CamIcuDeliriumFactors, CamIcuDeliriumScorer

findings = CamIcuDeliriumScorer().check(CamIcuDeliriumFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No network I/O.
