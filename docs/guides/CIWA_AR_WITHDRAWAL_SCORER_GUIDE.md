# CiwaArWithdrawalScorer Guide

![CiwaArWithdrawalScorer flow](../../assets/ciwa_ar_withdrawal_demo.gif)

Research-only advisory scorer (Safety #204). Never modifies medications.

Gap vs MDCalc / ASAM / EHR CIWA-Ar alcohol withdrawal score. Distinct from `GcsNeurologicStatusScorer / FallRiskChecker`.

Optional polish via **GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro**.

## Usage

```python
from medagent.safety.ciwa_ar_withdrawal_scorer import (
    CiwaArWithdrawalFactors,
    CiwaArWithdrawalScorer,
)

findings = CiwaArWithdrawalScorer().check(CiwaArWithdrawalFactors())
assert "RESEARCH USE ONLY" in findings[0].rationale
print(findings[0].band, findings[0].score)
```

## Safety

RESEARCH USE ONLY. See `SAFETY.md`.
