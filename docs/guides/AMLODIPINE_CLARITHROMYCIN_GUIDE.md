# Amlodipine + Clarithromycin Checker

![demo](../../assets/amlodipine_clarithromycin_demo.gif)

`AmlodipineClarithromycinChecker` — Amlodipine is a CYP3A4 substrate; clarithromycin is a strong CYP3A4 inhibitor. Co-prescription is linked to hospitalization for hypotension/shock in older adults. Distinct from simvastatin–macrolide and generic CCB panels.

Findings are advisory `AmlodipineClarithromycinRisk` records — **RESEARCH USE ONLY**.
Prefer GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 when summarizing.

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
```

## See also

- [SAFETY.md §3.114](../../SAFETY.md)
