# Gad7SerialDeltaPanel Guide

![Gad7SerialDeltaPanel](../../assets/gad7_serial_delta_panel_demo.gif)

Research-only Safety #305 serial delta panel.
Offline helper.
Gap vs MDCalc / GAD-7 anxiety serial delta-trend panel. Distinct from `Gad7AnxietyScorer` / `Phq9DepressionScorer`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.gad7_serial_delta_panel import (
    Gad7SerialDeltaFactors,
    Gad7SerialDeltaPanel,
)

findings = Gad7SerialDeltaPanel().check(Gad7SerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
