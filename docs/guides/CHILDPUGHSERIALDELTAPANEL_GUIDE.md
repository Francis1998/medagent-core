# ChildPughSerialDeltaPanel Guide

![ChildPughSerialDeltaPanel](../../assets/child_pugh_serial_delta_panel_demo.gif)

Research-only advisory panel (Safety #272).
Gap vs MDCalc / Child-Pugh serial delta-trend panel. Distinct from `ChildPughLiverSeverityScorer` / `MeldNaScorer`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.child_pugh_serial_delta_panel import (
    ChildPughSerialDeltaFactors,
    ChildPughSerialDeltaPanel,
)

findings = ChildPughSerialDeltaPanel().check(ChildPughSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies medications. No network I/O.
