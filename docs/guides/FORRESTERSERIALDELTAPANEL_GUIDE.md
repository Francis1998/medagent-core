# ForresterSerialDeltaPanel Guide

![ForresterSerialDeltaPanel](../../assets/forrester_serial_delta_panel_demo.gif)

Research-only Safety #292 serial delta panel.
Gap vs MDCalc / Forrester hemodynamic serial delta-trend panel. Distinct from `ForresterClassScorer` / `KillipSerialDeltaPanel`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

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
