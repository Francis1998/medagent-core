# ForresterSerialDeltaPanel Guide

![ForresterSerialDeltaPanel](../../assets/forrester_serial_delta_panel_demo.gif)

Research-only Safety #292 serial delta panel.
Gap vs MDCalc / Forrester hemodynamic serial delta-trend panel. Distinct from `ForresterClassScorer` / `KillipSerialDeltaPanel`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.forrester_serial_delta_panel import (
    ForresterSerialDeltaFactors,
    ForresterSerialDeltaPanel,
)

findings = ForresterSerialDeltaPanel().check(ForresterSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies therapy. No network I/O.
