# Phq9SerialDeltaPanel Guide

![Phq9SerialDeltaPanel](../../assets/phq9_serial_delta_panel_demo.gif)

Research-only Safety #304 serial delta panel.
Offline helper.
Gap vs MDCalc / PHQ-9 depression serial delta-trend panel. Distinct from `Phq9DepressionScorer` / `Gad7AnxietyScorer`.

Stack: **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.phq9_serial_delta_panel import (
    Phq9SerialDeltaFactors,
    Phq9SerialDeltaPanel,
)

findings = Phq9SerialDeltaPanel().check(Phq9SerialDeltaFactors())
print(findings[0].band, findings[0].rationale)
```

## Safety

Advisory only. No network I/O. Never auto-acts. Humans decide.
