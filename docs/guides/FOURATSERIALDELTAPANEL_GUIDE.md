# FourAtSerialDeltaPanel Guide

![FourAtSerialDeltaPanel](../../assets/four_at_serial_delta_panel_demo.gif)

Research-only Safety #293 serial delta panel.
Gap vs MDCalc / 4AT delirium serial delta-trend panel. Distinct from `FourAtDeliriumScorer` / `FourScoreSerialDeltaPanel`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.four_at_serial_delta_panel import (
    FourAtSerialDeltaFactors,
    FourAtSerialDeltaPanel,
)

findings = FourAtSerialDeltaPanel().check(FourAtSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies therapy. No network I/O.
