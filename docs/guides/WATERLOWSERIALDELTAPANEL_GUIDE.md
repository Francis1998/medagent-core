# WaterlowSerialDeltaPanel Guide

![WaterlowSerialDeltaPanel](../../assets/waterlow_serial_delta_panel_demo.gif)

Research-only Safety #301 serial delta panel.
Offline helper.
Gap vs MDCalc / Waterlow pressure-ulcer serial delta-trend panel. Distinct from `BradenSerialDeltaPanel` / `BradenPressureScorer`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.waterlow_serial_delta_panel import (
    WaterlowSerialDeltaFactors,
    WaterlowSerialDeltaPanel,
)

findings = WaterlowSerialDeltaPanel().check(WaterlowSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
