# LamsStrokeScaleScorer Guide

![LamsStrokeScaleScorer demo](../../assets/lams-stroke-scale_demo.gif)

Research-only advisory scorer. Never modifies medications. Gap vs MDCalc / AHA LAMS large-vessel occlusion screen.

Optional narrative via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

Distinct from `NihssStrokeScorer / RaceStrokeScaleScorer`.

## Usage

```python
from medagent.safety.lams_stroke_scale_scorer import (
    LamsStrokeScaleFactors,
    LamsStrokeScaleScorer,
)

findings = LamsStrokeScaleScorer().check(LamsStrokeScaleFactors())
print(findings[0].band, findings[0].rationale)
```
