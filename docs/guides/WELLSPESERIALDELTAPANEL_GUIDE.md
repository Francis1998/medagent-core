# WellsPeSerialDeltaPanel Guide

![WellsPeSerialDeltaPanel](../../assets/wells_pe_serial_delta_panel_demo.gif)

Research-only advisory panel. Gap vs MDCalc / Wells PE serial delta-trend panel.
Distinct from `WellsPeProbabilityScorer` / `PsiPortPneumoniaScorer`.

Narrative polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.wells_pe_serial_delta_panel import (
    WellsPeSerialDeltaFactors,
    WellsPeSerialDeltaPanel,
)

findings = WellsPeSerialDeltaPanel().check(WellsPeSerialDeltaFactors())
assert findings[0].rationale
```

## Safety

RESEARCH USE ONLY. Advisory. Never modifies medications. No network I/O.
