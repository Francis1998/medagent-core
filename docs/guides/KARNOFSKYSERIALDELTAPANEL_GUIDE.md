# KarnofskySerialDeltaPanel Guide

![KarnofskySerialDeltaPanel](../../assets/karnofsky_serial_delta_panel_demo.gif)

Research-only Safety #296 serial delta panel.
Offline helper.
Gap vs MDCalc / Karnofsky performance serial delta-trend panel. Distinct from `KarnofskyPerformanceScorer` / `EcogSerialDeltaPanel`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.karnofsky_serial_delta_panel import (
    KarnofskySerialDeltaFactors,
    KarnofskySerialDeltaPanel,
)

findings = KarnofskySerialDeltaPanel().check(KarnofskySerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
