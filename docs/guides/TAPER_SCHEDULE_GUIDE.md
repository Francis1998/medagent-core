# Taper-Schedule Advisory Checker Guide

*medagent-core — Safety Control #29*

![Taper-schedule advisory checker flow](../../assets/taper_schedule_demo.gif)

## Overview

`TaperScheduleChecker` flags conservative medication patterns where abrupt
discontinuation may be unsafe or poorly tolerated and where a qualified clinician
should review whether individualized taper planning is appropriate.

The checker covers chronic/scheduled exposure to:

- opioids
- benzodiazepines and Z-drug hypnotics
- proton-pump inhibitors (PPIs)
- SSRIs and SNRIs

Findings are advisory `TaperScheduleRisk` records — **RESEARCH USE ONLY**, not
clinical advice, not a prescription, and not a patient-specific taper schedule.
The checker is exported from `medagent.safety` and never modifies a medication
list.

## Conservative panel

| Class | Example triggers | Severity | Main abrupt-stop concern |
|---|---|---|---|
| Opioids | scheduled/chronic morphine, oxycodone, hydrocodone, hydromorphone, methadone, fentanyl, tramadol | HIGH | withdrawal, pain destabilization, psychological distress |
| Benzodiazepines/Z-drugs | scheduled/chronic alprazolam, clonazepam, diazepam, lorazepam, temazepam, zolpidem, eszopiclone, zaleplon | HIGH | withdrawal, rebound anxiety/insomnia, seizures, delirium |
| PPIs | long-term omeprazole, pantoprazole, esomeprazole, lansoprazole | LOW | rebound acid hypersecretion and symptom relapse |
| SSRIs/SNRIs | scheduled/chronic sertraline, fluoxetine, paroxetine, citalopram, escitalopram, venlafaxine, desvenlafaxine, duloxetine | MODERATE | discontinuation syndrome and symptom relapse |

Medication matching is whole-token based: `oxycodonelike` does not match
`oxycodone`, and `sertralinesque` does not match `sertraline`. A scheduled or
chronic-use cue (for example `daily`, `BID`, `nightly`, `maintenance`, `patch`,
`long-term`, or `extended release`) is required before any finding is emitted.

PPI findings are suppressed when optional indication text includes a protective
high-risk GI indication such as Barrett esophagus, erosive esophagitis, prior GI
bleed, peptic ulcer, gastroprotection, or Zollinger-Ellison syndrome.

## Quick start

```python
from medagent.models import Medication
from medagent.safety import TaperScheduleChecker

findings = TaperScheduleChecker().check(
    medications=[
        Medication(name="Oxycodone ER 20 mg", frequency="BID"),
        Medication(name="Ambien 5 mg", frequency="nightly"),
        Medication(name="Sertraline 100 mg", frequency="daily"),
        Medication(name="Pantoprazole 40 mg", frequency="daily"),
    ],
    indications=["GERD symptoms resolved"],
)
for finding in findings:
    print(
        finding.agent,
        finding.medication_class,
        finding.taper_opportunity,
        finding.severity,
        finding.suggested_review,
    )
```

## Output contract

Each `TaperScheduleRisk` includes:

- `medication` and canonical `agent`
- `medication_class` (`opioid`, `benzodiazepine_z_drug`, `ppi`, `ssri`, or
  `snri`)
- `taper_opportunity`
- `suggested_review` (non-prescriptive clinician review language)
- `abrupt_stop_concern`
- `taper_candidate`
- `severity`
- `rationale`

The rationale always states **RESEARCH USE ONLY** and explicitly notes that the
checker does not prescribe, stop, or auto-generate a taper schedule.

## Reasoning stack notes

When this checker's findings are summarized by an upstream reasoning / routing
layer, prefer current frontier models for clinical prose:

- **GPT-5.5**
- **Claude Sonnet 4.6**
- **Gemini 3.x**
- **Kimi K2**

The checker itself is deterministic and does not call an LLM.

## See also

- [SAFETY.md §3.29](../../SAFETY.md)
- [README safety controls table](../../README.md)
- [CHANGELOG](../../CHANGELOG.md)
- Related safety checks: `safety/geriatric_deprescribing_checker.py`,
  `safety/opioid_med_checker.py`, `safety/beers_criteria_checker.py`,
  `safety/stopp_start_checker.py`
