# PsiSerialDeltaPanel Guide

![PsiSerialDeltaPanel](../../assets/psi_serial_delta_panel_demo.gif)

Research-only advisory panel. Gap vs MDCalc / PSI/PORT serial delta-trend panel.
Distinct from `PsiPortPneumoniaScorer` / `Curb65SerialDeltaPanel`.

Narrative polish via **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.psi_serial_delta_panel import PsiSerialDeltaFactors, PsiSerialDeltaPanel

findings = PsiSerialDeltaPanel().check(PsiSerialDeltaFactors())
assert findings[0].rationale
```

## Safety

RESEARCH USE ONLY. Advisory. Never modifies medications. No network I/O.
