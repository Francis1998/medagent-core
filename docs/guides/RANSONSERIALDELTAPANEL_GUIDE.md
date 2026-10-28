# RansonSerialDeltaPanel Guide

![RansonSerialDeltaPanel](../../assets/ranson_serial_delta_panel_demo.gif)

Research-only Safety #277.
Gap vs MDCalc / Ranson serial delta-trend panel. Distinct from `RansonPancreatitisScorer` / `BisapPancreatitisScorer`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.ranson_serial_delta_panel import (
    RansonSerialDeltaFactors,
    RansonSerialDeltaPanel,
)

findings = RansonSerialDeltaPanel().check(RansonSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Advisory. Never modifies medications. No network I/O.
