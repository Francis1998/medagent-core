# Clinical Guideline Matcher Guide

*medagent-core — Safety Control #132*

![Clinical guideline matcher flow](../../assets/clinical_guideline_matcher_demo.gif)

## Overview

`ClinicalGuidelineMatcher` matches patient conditions to a curated
**educational clinical-guideline panel** (HFrEF GDMT cues, hypertension
first-line classes, and similar). Findings are advisory `GuidelineMatch`
records — **RESEARCH USE ONLY**.

Prefer frontier reasoning models when summarizing findings: **GPT-5.5**,
**Claude Sonnet 4.6**, **Gemini 3.x**, **Kimi K2**.

## Gap vs DiseaseContraindicationChecker

`DiseaseContraindicationChecker` flags **condition × drug contraindications**
(HF + NSAID). This matcher surfaces **positive guideline-awareness cues** for
the same condition vocabulary without requiring a contraindicated drug.

## Curated guidelines

| Guideline ID | Condition | Educational focus |
|---|---|---|
| hf_gdmt | HFrEF | ARNI/ACEi/ARB, BB, MRA, SGLT2 building blocks |
| hf_general_gdmt_cue | heart failure / CHF | GDMT awareness |
| htn_first_line | hypertension | thiazide-like / CCB / ACEi / ARB |
| t2dm_cardiorenal | type 2 diabetes | metformin + SGLT2i/GLP-1 cues |
| ckd_acei_sglt2 | CKD | ACEi/ARB + SGLT2 cues |
| afib_stroke_prevention | atrial fibrillation | anticoagulation awareness |
| ascvd_secondary_prevention | CAD / ASCVD | high-intensity statin / antiplatelet |

## Quick start

```python
from medagent.models import Medication
from medagent.safety import ClinicalGuidelineMatcher

findings = ClinicalGuidelineMatcher().check(
    conditions=["HFrEF", "Hypertension"],
    medications=[
        Medication(name="Dapagliflozin 10mg"),
        Medication(name="Amlodipine 5mg"),
    ],
)
for finding in findings:
    print(finding.guideline_id, finding.present_cue_agents, finding.rationale)
```

## Safety

Advisory only; never auto-modifies medications or prescribes therapy.
**RESEARCH USE ONLY.**
