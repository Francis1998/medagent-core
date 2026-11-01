# WfnsSerialDeltaPanel Guide

![WfnsSerialDeltaPanel](../../assets/wfns_serial_delta_panel_demo.gif)

Research-only Safety #291 serial delta panel.
Gap vs MDCalc / WFNS SAH serial delta-trend panel. Distinct from `WfnsSahScorer` / `HuntHessSerialDeltaPanel`.

Stack: **GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2**.

## Usage

```python
from medagent.safety.wfns_serial_delta_panel import WfnsSerialDeltaFactors, WfnsSerialDeltaPanel

findings = WfnsSerialDeltaPanel().check(WfnsSerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

RESEARCH USE ONLY. Never modifies therapy. No network I/O.
