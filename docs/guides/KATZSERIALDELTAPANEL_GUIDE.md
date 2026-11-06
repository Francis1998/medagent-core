# KatzSerialDeltaPanel Guide

![KatzSerialDeltaPanel](../../assets/katz_serial_delta_panel_demo.gif)

Research-only Safety #306 serial delta panel.
Offline helper.
Gap vs MDCalc / Katz ADL serial delta-trend panel. Distinct from `BarthelSerialDeltaPanel` / `KarnofskySerialDeltaPanel`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.katz_serial_delta_panel import (
    KatzSerialDeltaFactors,
    KatzSerialDeltaPanel,
)

findings = KatzSerialDeltaPanel().check(KatzSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
