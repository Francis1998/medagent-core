# Combined Renal + Hepatic + Lactation Checker Guide

*medagent-core — Safety Control #34*

![Combined renal + hepatic + lactation checker flow](../../assets/renal_hepatic_lactation_demo.gif)

## Overview

`RenalHepaticLactationChecker` unifies organ-impairment dose cautions (renal
eGFR and/or hepatic Child-Pugh) with the lactation / breastfeeding checker into
one panel. It complements the standalone renal, hepatic, combined renal+hepatic,
and lactation checkers by surfacing three finding kinds:

| Concern kind | When emitted |
|---|---|
| `combined` | `breastfeeding=True` and the same medication matches organ (renal and/or hepatic) **and** lactation panels |
| `organ_only` | Renal and/or hepatic dose concern without a lactation match (or when not breastfeeding) |
| `lactation_only` | `breastfeeding=True` and the medication matches the lactation panel only |

Combined findings escalate severity **one rank** above the maximum of the organ
and lactation component severities (capped at `CRITICAL`). Overlapping agents
such as **methotrexate**, **amiodarone**, **codeine**, and **tramadol**
illustrate why dual organ-function and breastfeeding exposure deserves a
distinct alert.

Findings are advisory `RenalHepaticLactationRisk` records — **RESEARCH USE
ONLY** — and the checker is exported from `medagent.safety`.

## How findings are composed

| Step | Rule |
|---|---|
| Renal component | Run `RenalDoseChecker.check(medications, egfr)` when eGFR is known |
| Hepatic component | Run `HepaticDoseChecker.check(medications, hepatic_function)` when Child-Pugh class is known |
| Lactation component | Run `LactationSafetyChecker.check(medications, breastfeeding=True)` when `breastfeeding=True` |
| Organ merge | Same medication display name; organ severity is `max(renal, hepatic)` of components that fired |
| Join key | Same `medication` display name across organ and lactation findings |
| Combined severity | One rank above `max(organ_severity, lactation_severity)`, capped at `CRITICAL` |
| Missing status | No organ data **and** not breastfeeding returns no findings |

Matching stays deterministic because the component checkers already use
whole-token / whole-phrase medication matching.

## Quick start

```python
from medagent.models import HepaticFunction, Medication
from medagent.safety import RenalHepaticLactationChecker

findings = RenalHepaticLactationChecker().check(
    medications=[
        Medication(name="Methotrexate 15mg"),
        Medication(name="Ibuprofen 400mg"),
        Medication(name="Lithium carbonate"),
    ],
    egfr=25.0,
    hepatic_function=HepaticFunction.MODERATE,
    breastfeeding=True,
)
for finding in findings:
    print(
        finding.concern_kind,
        finding.agent,
        finding.severity,
        finding.organ_severity,
        finding.lactation_severity,
        finding.rationale,
    )
```

## Reasoning stack notes

When this checker’s findings are summarized by an upstream reasoning / routing
layer, prefer current frontier models for clinical prose:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.34](../../SAFETY.md)
- [README safety controls table](../../README.md)
- [CHANGELOG](../../CHANGELOG.md)
- Combined renal + hepatic: `safety/combined_renal_hepatic_checker.py`
- Lactation safety: `safety/lactation_checker.py`
- Pregnancy + lactation panel: `safety/pregnancy_lactation_checker.py`
