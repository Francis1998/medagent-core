# GcsSerialDeltaPanel Guide

![GcsSerialDeltaPanel](../../assets/gcs_serial_delta_panel_demo.gif)

Research-only advisory panel (Safety #276).
Gap vs MDCalc / GCS serial delta-trend panel. Distinct from `GcsNeurologicStatusScorer` / `NihssSerialDeltaPanel`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.gcs_serial_delta_panel import (
    GcsSerialDeltaFactors,
    GcsSerialDeltaPanel,
)

findings = GcsSerialDeltaPanel().check(GcsSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No network I/O.
