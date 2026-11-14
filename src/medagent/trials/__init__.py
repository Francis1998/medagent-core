"""Research-only clinical-trial eligibility pre-screening.

Evaluates one patient's FHIR R4 Bundle, normalised and de-identified by the
MCP ``parse_fhir_bundle`` path, against structured trial definitions (the
ClinicalTrials.gov API v2 ``eligibilityModule`` fields plus structured
inclusion and exclusion criteria). Every criterion is ``met``, ``not_met``,
``insufficient_data`` or ``requires_human_review`` with evidence pointers, and
trials are ranked deterministically. It never determines eligibility, never
enrolls or contacts anyone, and never guesses free-text criteria.

Import from the submodules, e.g. ``from medagent.trials.screening import
screen_trials``. This package module deliberately imports nothing:
``medagent.mcp.tools`` registers the ``screen_trial_eligibility`` tool from
``medagent.trials.schema``, while the screening code reuses the MCP layer's
FHIR normalisation, so eager re-exports here would create an import cycle.

RESEARCH USE ONLY. Not FDA-cleared.
"""
