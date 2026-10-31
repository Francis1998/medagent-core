# GlasgowBlatchfordSerialDeltaPanel Guide

![GlasgowBlatchfordSerialDeltaPanel](../../assets/glasgow_blatchford_serial_delta_panel_demo.gif)

Research-only serial delta panel (Safety #288).
Gap vs MDCalc / Glasgow-Blatchford GI bleed serial delta-trend panel. Distinct from `GlasgowBlatchfordScorer` / `RockallGiBleedScorer`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.glasgow_blatchford_serial_delta_panel import (
    GlasgowBlatchfordSerialDeltaFactors,
    GlasgowBlatchfordSerialDeltaPanel,
)

findings = GlasgowBlatchfordSerialDeltaPanel().check(GlasgowBlatchfordSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Advisory. Never modifies medications. No network I/O.
