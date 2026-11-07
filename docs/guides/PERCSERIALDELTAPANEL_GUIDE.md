# PercSerialDeltaPanel Guide

![PercSerialDeltaPanel](../../assets/perc_serial_delta_panel_demo.gif)

Research-only advisory panel (Safety #268).
Gap vs MDCalc / PERC serial delta-trend panel. Distinct from `PercPeExclusionScorer` / `WellsPeSerialDeltaPanel`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.perc_serial_delta_panel import (
    PercSerialDeltaFactors,
    PercSerialDeltaPanel,
)

findings = PercSerialDeltaPanel().check(PercSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No network I/O.
