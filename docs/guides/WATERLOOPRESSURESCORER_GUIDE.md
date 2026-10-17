# WaterlooPressureScorer Guide

![WaterlooPressureScorer](../../assets/waterloo_pressure_scorer_demo.gif)

Research-only advisory scorer. Gap vs MDCalc / Waterloo pressure-injury risk screen.
Distinct from `BradenPressureScorer` / `MorseFallScorer`. Safety #246.

Narrative polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.waterloo_pressure_scorer import WaterlooPressureFactors, WaterlooPressureScorer

findings = WaterlooPressureScorer().check(WaterlooPressureFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No network I/O.
