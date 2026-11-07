# AlvaradoSerialDeltaPanel Guide

![AlvaradoSerialDeltaPanel](../../assets/alvarado_serial_delta_panel_demo.gif)

Research-only advisory panel (Safety #274).
Gap vs MDCalc / Alvarado serial delta-trend panel. Distinct from `AlvaradoAppendicitisScorer` / `CentorSerialDeltaPanel`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.alvarado_serial_delta_panel import (
    AlvaradoSerialDeltaFactors,
    AlvaradoSerialDeltaPanel,
)

findings = AlvaradoSerialDeltaPanel().check(AlvaradoSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No network I/O.
