# KillipSerialDeltaPanel Guide

![KillipSerialDeltaPanel](../../assets/killip_serial_delta_panel_demo.gif)

Research-only advisory panel (Safety #269).
Gap vs MDCalc / Killip serial delta-trend panel. Distinct from `KillipClassScorer` / `HeartSerialDeltaPanel`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.killip_serial_delta_panel import (
    KillipSerialDeltaFactors,
    KillipSerialDeltaPanel,
)

findings = KillipSerialDeltaPanel().check(KillipSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No network I/O.
