# RaceStrokeScaleScorer Guide

![RaceStrokeScaleScorer demo](../../assets/race-stroke-scale_demo.gif)

Research-only advisory scorer. Never modifies medications. Gap vs MDCalc / AHA RACE stroke scale.

Optional narrative via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

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
