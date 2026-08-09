# DOAC + Antiplatelet Bleed Intensifier Checker Guide

*medagent-core — Safety Control #57*

![DOAC antiplatelet checker flow](../../assets/doac_antiplatelet_demo.gif)

## Overview

`DoacAntiplateletChecker` flags **DOAC agents** (apixaban, rivaroxaban,
edoxaban, dabigatran) co-prescribed with **antiplatelet partners** (aspirin,
clopidogrel, prasugrel, ticagrelor). Concurrent DOAC anticoagulation with
antiplatelet therapy intensifies major bleeding risk.

Findings are advisory `DoacAntiplateletRisk` records — **RESEARCH USE ONLY** —
and the checker is exported from `medagent.safety`. Severity is always
**HIGH**.

## DOAC panel

| Agent | Notes |
|---|---|
| apixaban | factor Xa inhibitor DOAC |
| rivaroxaban | factor Xa inhibitor DOAC |
| edoxaban | factor Xa inhibitor DOAC |
| dabigatran | direct thrombin inhibitor DOAC |

## Antiplatelet partners

| Agent | Notes |
|---|---|
| aspirin | antiplatelet |
| clopidogrel | P2Y12 inhibitor |
| prasugrel | P2Y12 inhibitor |
| ticagrelor | P2Y12 inhibitor |

Every DOAC × antiplatelet pair yields one finding. Medication matching is
whole-token based.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import DoacAntiplateletChecker

findings = DoacAntiplateletChecker().check(
    medications=[
        Medication(name="Apixaban 5 mg BID"),
        Medication(name="Aspirin 81 mg daily"),
    ],
)
for finding in findings:
    print(
        finding.agent,
        finding.partner_agent,
        finding.severity,
        finding.rationale,
    )
```

## Reasoning stack notes

When this checker's findings are summarized by an upstream reasoning / routing
layer, prefer current frontier models for clinical prose:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## Suggested repo description / topics

**Description:** Research-only medical agent core with deterministic safety
checkers and modern LLM adapters (GPT-5.5, Claude Sonnet 4.6, Gemini 3.x,
Kimi K2).

**Topics:** `medical-ai`, `drug-safety`, `doac`, `antiplatelet`, `agentic-ai`,
`python`

## See also

- [SAFETY.md §3.57](../../SAFETY.md)
- [README safety controls table](../../README.md)
