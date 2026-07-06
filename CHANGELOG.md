# Changelog

All notable changes to **medagent-core** are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- Duplicate-therapy detector (`safety/duplicate_therapy.py`) that groups active medications by therapeutic class and flags classes containing two or more distinct agents (anticoagulants, SSRIs, benzodiazepines, opioids, NSAIDs, ACE inhibitors, statins, PPIs) as `DuplicateTherapy` records. The same drug listed twice is not flagged. Documented as Safety Control #10 (SAFETY.md §3.10).
- Drug-allergy conflict checker (`safety/allergy_checker.py`) that cross-checks active medications against documented patient allergies, flagging direct conflicts and intra-class cross-reactivity (penicillins, cephalosporins, sulfonamides, NSAIDs) as `AllergyConflict` records. Documented as Safety Control #9 (SAFETY.md §3.9).

### Fixed
- RxNorm severity mapping now resolves `N/A` (unrated) interactions to `UNKNOWN` instead of silently defaulting to `MODERATE`; the mapping key was uppercase while the lookup lowercased its input, so the `N/A` entry was unreachable and overstated the severity of interactions with no documented rating.
- `_extract_age` now applies the birthday-not-yet-reached adjustment to partial `YYYY-MM` FHIR `birthDate` values using the month, instead of only full `YYYY-MM-DD` dates, which overstated age by up to a year for such dates.
- `sanitise_clinical_text` now redacts US Social Security numbers (`NNN-NN-NNNN`) in free-text clinical notes; SSNs are listed as PII in the de-identification contract but no prior pattern matched their 3-2-4 shape, so they leaked into LLM prompts unredacted.
- `sanitise_clinical_text` now redacts ISO-8601 (`YYYY-MM-DD`, the FHIR `birthDate` format) and `DD-Mon-YYYY` date-of-birth patterns in free-text clinical notes; previously only `MM/DD/YYYY`-style dates were redacted, leaking ISO dates into LLM prompts.

## [v0.7.19] — 2026-03-13

### Added
- Extended drug module with improved error handling
- Added structured logging for reasoning operations
- New unit tests covering edge cases in audit pipeline

### Changed
- Refactored retry logic to use exponential backoff with jitter
- Improved type annotations across core modules
- Updated dependency pins to latest stable versions

### Fixed
- Resolved race condition in async drug handler
- Fixed incorrect reasoning timeout calculation

## [v0.1.0] — 2026-02-06

### Added
- Initial project scaffold with biomedical AI core
- Basic medagent implementation
- README and setup documentation
