# Changelog

All notable changes to **medagent-core** are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- Serotonin-syndrome checker (`safety/serotonin_syndrome_checker.py`) that flags active medications with serotonergic activity (SSRIs, SNRIs, MAOIs, serotonergic tricyclics, triptans, serotonergic opioids, and others) as `SerotoninSyndromeRisk` records. Because serotonin syndrome arises from the *combination* of agents, a lone serotonergic drug yields no finding; two or more are `HIGH`, and any MAOI in the combination escalates every finding to `CRITICAL` (an MAOI plus another serotonergic agent is contraindicated). Whole-token matching avoids substring false positives. Documented as Safety Control #14 (SAFETY.md §3.14).

### Fixed
- `sanitise_clinical_text` did not redact phone numbers with a parenthesised area code (`(415) 555-1234`) or a leading country code (`+1 415-555-1234`): the pattern's leading `\b` could not match before the `(`, so such numbers leaked into text passed to the LLM. The pattern now uses `(?<!\w)`/`(?!\w)` boundaries and accepts a parenthesised area code and optional country code, while still requiring a separator (or parentheses) so a bare ten-digit sequence is not treated as a phone.

### Added (earlier this cycle)
- Anticholinergic-burden checker (`safety/anticholinergic_burden_checker.py`) that scores active medications on the Anticholinergic Cognitive Burden (ACB) scale (1–3) and sums them into a total burden, emitting `AnticholinergicBurdenRisk` records. Because the harm (confusion, falls, urinary retention, cognitive decline) is cumulative rather than tied to a single agent, a finding's severity is elevated to at least `HIGH` when the total reaches the clinically significant threshold (≥3). Whole-token matching avoids substring false positives. Documented as Safety Control #13 (SAFETY.md §3.13).
- QT-prolongation checker (`safety/qt_prolongation_checker.py`) that flags active medications matching a known QT-prolonging agent (antiarrhythmics, methadone, antipsychotics, citalopram/escitalopram, macrolide and fluoroquinolone antibiotics, ondansetron, fluconazole) as `QTProlongationRisk` records. Because torsadogenic risk is additive, a finding's severity is elevated to at least `HIGH` and the concurrent QT-medication count is recorded whenever two or more QT-prolonging drugs are co-prescribed. Whole-token matching avoids substring false positives. Documented as Safety Control #12 (SAFETY.md §3.12).
- Pregnancy-safety checker (`safety/pregnancy_checker.py`) that flags active medications matching a known teratogen or pregnancy-contraindicated agent (isotretinoin, methotrexate, warfarin, valproate, phenytoin, lithium, ACE inhibitors, ARBs, tetracyclines, and more) as `PregnancyRisk` records. Gated on a `pregnant` flag so it returns no findings for non-pregnant patients; whole-token matching avoids substring false positives. Documented as Safety Control #11 (SAFETY.md §3.11).
- Duplicate-therapy detector (`safety/duplicate_therapy.py`) that groups active medications by therapeutic class and flags classes containing two or more distinct agents (anticoagulants, SSRIs, benzodiazepines, opioids, NSAIDs, ACE inhibitors, statins, PPIs) as `DuplicateTherapy` records. The same drug listed twice is not flagged. Documented as Safety Control #10 (SAFETY.md §3.10).
- Drug-allergy conflict checker (`safety/allergy_checker.py`) that cross-checks active medications against documented patient allergies, flagging direct conflicts and intra-class cross-reactivity (penicillins, cephalosporins, sulfonamides, NSAIDs) as `AllergyConflict` records. Documented as Safety Control #9 (SAFETY.md §3.9).

### Fixed
- Reasoning engine `_parse_llm_response` now accepts evidence items given as bare strings (for example `"evidence_for": ["fever", "cough"]`), not only `{"statement": ..., "strength": ...}` objects. The previous code called `.get("statement")` on each item, so a string raised `AttributeError` that was caught one level up and silently discarded the *entire* hypothesis; string items now become the statement with a neutral default strength, and out-of-range/uncoercible strengths are clamped rather than dropping the item.
- Reasoning engine `_parse_llm_response` now strips the markdown code-fence language tag case-insensitively (```` ```JSON ````, ```` ```json ````, or a bare ```` ``` ````). The previous case-sensitive `(?:json)?` pattern left an uppercase `JSON` tag in the payload, so `json.loads` raised and every hypothesis was silently dropped, forcing the low-confidence fallback path for models that emit an uppercase fence.
- PubMed `_parse_article` now parses a bare-string `PMID` (which NCBI JSON emits when a single-valued element has no attributes) instead of raising `AttributeError`. The parser called `.get("#text")` on the value before its own string fallback could run, so the `AttributeError` was swallowed by the caller and the article was silently dropped; the value is now normalized through `_extract_text`, which handles both the string and `{"#text": ...}` shapes.
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
