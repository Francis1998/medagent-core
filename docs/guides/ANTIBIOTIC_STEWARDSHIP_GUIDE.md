# Antibiotic Stewardship Checker Guide

*medagent-core — Safety Control #24*

![Antibiotic stewardship checker flow](../../assets/antibiotic_stewardship_demo.gif)

## Overview

`AntibioticStewardshipChecker` flags high-risk antimicrobial-use patterns that
are not covered by the drug-allergy, duplicate-therapy, QT, renal/hepatic dose,
or STOPP/START checkers:

- fluoroquinolones without a documented infectious indication
- duplicate antimicrobial coverage across distinct agents
- prolonged-course cues such as `for 21 days`, `3 week course`, `day 15 of
  therapy`, or chronic/suppressive language

Findings are advisory `AntibioticStewardshipRisk` records — RESEARCH USE ONLY —
and the checker is standalone (not exported from `safety/__init__.py` or wired
into the orchestrator).

## Conservative panel

| Concern | Trigger | Severity |
|---|---|---|
| Fluoroquinolone without indication | ciprofloxacin, levofloxacin, moxifloxacin, ofloxacin, or delafloxacin without recognized indication context | HIGH |
| Duplicate coverage | two or more distinct agents in a modeled coverage class (anaerobic, MRSA, macrolide, fluoroquinolone, antipseudomonal beta-lactam) | HIGH |
| Prolonged duration | antibiotic duration cue >14 days, or chronic/long-term/suppressive/indefinite language | MODERATE |

Medication matching is whole-token based: `ciprofloxacinoid` does not match
`ciprofloxacin`, and duplicate entries for the same canonical agent (for example
two vancomycin reconciliation lines) do not count as duplicate coverage.

## Quick start

```python
from medagent.models import Medication
from medagent.safety.antibiotic_stewardship_checker import AntibioticStewardshipChecker

findings = AntibioticStewardshipChecker().check(
    medications=[
        Medication(name="Ciprofloxacin 500 mg BID"),
        Medication(name="Metronidazole 500 mg IV q8h"),
        Medication(name="Piperacillin-tazobactam 4.5 g IV q6h"),
    ],
    indications=["abdominal pain, cultures pending"],
)
for finding in findings:
    print(finding.concern, finding.agents, finding.severity, finding.rationale)
```

## Reasoning stack notes

When this checker’s findings are summarized by an upstream reasoning / routing
layer, prefer current frontier models for clinical prose:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 2.5**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.24](../../SAFETY.md)
- [README safety controls table](../../README.md)
- [CHANGELOG](../../CHANGELOG.md)
- Related safety checks: `safety/drug_food_interaction_checker.py`,
  `safety/renal_dose_checker.py`, `safety/hepatic_dose_checker.py`
