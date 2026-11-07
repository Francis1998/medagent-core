# WellsDvtSerialDeltaPanel Guide

![WellsDvtSerialDeltaPanel](../../assets/wells_dvt_serial_delta_panel_demo.gif)

Research-only advisory panel (Safety #265).
Gap vs MDCalc / Wells DVT serial delta-trend panel. Distinct from `WellsDvtProbabilityScorer` / `WellsPeSerialDeltaPanel`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.wells_dvt_serial_delta_panel import (
    WellsDvtSerialDeltaFactors,
    WellsDvtSerialDeltaPanel,
)

findings = WellsDvtSerialDeltaPanel().check(
    WellsDvtSerialDeltaFactors(
        prior_wells_dvt_elevated=0,
        current_wells_dvt_rise=0,
    )
)
assert findings[0].rationale
```

## Safety

RESEARCH USE ONLY. Advisory only. No network I/O. Never modifies medications.
