# RaceStrokeScaleScorer Guide

![RaceStrokeScaleScorer demo](../../assets/race-stroke-scale_demo.gif)

Research-only advisory scorer. Never modifies medications. Gap vs MDCalc / AHA RACE stroke scale.

Optional narrative via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

Distinct from `NihssStrokeScorer / CincinnatiPrehospitalStrokeScorer`.

## Usage

```python
from medagent.safety.race_stroke_scale_scorer import (
    RaceStrokeScaleFactors,
    RaceStrokeScaleScorer,
)

findings = RaceStrokeScaleScorer().check(RaceStrokeScaleFactors())
print(findings[0].band, findings[0].rationale)
```
