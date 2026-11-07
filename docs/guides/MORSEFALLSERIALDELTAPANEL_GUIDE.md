# MorseFallSerialDeltaPanel Guide

![MorseFallSerialDeltaPanel](../../assets/morse_fall_serial_delta_panel_demo.gif)

Research-only Safety #299 serial delta panel.
Offline helper.
Gap vs MDCalc / Morse Fall Scale serial delta-trend panel. Distinct from `MorseFallScorer` / `BradenPressureScorer`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.morse_fall_serial_delta_panel import (
    MorseFallSerialDeltaFactors,
    MorseFallSerialDeltaPanel,
)

findings = MorseFallSerialDeltaPanel().check(MorseFallSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
