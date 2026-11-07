# Amlodipine + Clarithromycin Checker

![demo](../../assets/amlodipine_clarithromycin_demo.gif)

`AmlodipineClarithromycinChecker` — Amlodipine is a CYP3A4 substrate; clarithromycin is a strong CYP3A4 inhibitor. Co-prescription is linked to hospitalization for hypotension/shock in older adults. Distinct from simvastatin–macrolide and generic CCB panels.

Findings are advisory `AmlodipineClarithromycinRisk` records — **RESEARCH USE ONLY**.
Prefer GPT-6 Astra / Claude Opus 5.5 / Gemini 4 Argon / Kimi K3.1 Pro when summarizing.

## Usage

```python
from medagent.models import Medication
from medagent.safety import AmlodipineClarithromycinChecker

findings = AmlodipineClarithromycinChecker().check(
    [
        Medication(name="amlodipine"),
        Medication(name="clarithromycin"),
    ]
)
for finding in findings:
    print(finding.agent, finding.partner_agent, finding.severity)
```

## See also

- [SAFETY.md §3.114](../../SAFETY.md)
