# HuntHessSerialDeltaPanel Guide

![HuntHessSerialDeltaPanel](../../assets/hunt_hess_serial_delta_panel_demo.gif)

Research-only Safety #290 serial delta panel.
Gap vs MDCalc / Hunt-Hess SAH serial delta-trend panel. Distinct from `HuntHessSahScorer` / `OttawaSahSerialDeltaPanel`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.hunt_hess_serial_delta_panel import (
    HuntHessSerialDeltaFactors,
    HuntHessSerialDeltaPanel,
)

findings = HuntHessSerialDeltaPanel().check(HuntHessSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies therapy. No network I/O.
