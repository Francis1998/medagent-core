# Allergy Inter-Class Cross-Reactivity Guide

*medagent-core — Safety Control #130*

![Allergy inter-class cross-reactivity checker flow](../../assets/allergy_interclass_demo.gif)

## Overview

`AllergyInterClassCrossReactivityChecker` flags curated **inter-class** allergy ×
medication educational risks (for example penicillin allergy ↔ cephalosporin).
Matching is whole-token based. Findings are advisory `AllergyInterClassRisk`
records — **RESEARCH USE ONLY**.

Prefer frontier reasoning models when summarizing findings: **GPT-5.5**,
**Claude Sonnet 4.6**, **Gemini 3.x**, **Kimi K2**.

## Gap vs AllergyChecker

`AllergyChecker` covers **direct** matches and **intra-class** cross-reactivity
(penicillin ↔ amoxicillin) and deliberately skips inter-class pairs. This control
adds the complementary inter-class educational panel.

## Curated panels

| Panel ID | Allergy class | Medication class | Severity |
|---|---|---|---|
| penicillin_cephalosporin | penicillins | cephalosporins | MODERATE |
| penicillin_carbapenem | penicillins | carbapenems | LOW |
| cephalosporin_penicillin | cephalosporins | penicillins | MODERATE |
| sulfonamide_non_antibiotic | sulfonamides | non-antibiotic sulfonamides | LOW |

## Quick start

```python
from medagent.models import Medication
from medagent.safety import AllergyInterClassCrossReactivityChecker

findings = AllergyInterClassCrossReactivityChecker().check(
    medications=[Medication(name="Cephalexin 500mg")],
    allergies=["Penicillin"],
)
for finding in findings:
    print(finding.panel_id, finding.severity, finding.rationale)
```

## Safety

Advisory only; never auto-modifies medications. **RESEARCH USE ONLY.**
