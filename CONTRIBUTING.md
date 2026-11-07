# Contributing to medagent-core

Thanks for helping make clinical AI research safer. medagent-core is **research software and not
for clinical use** (see [SAFETY.md](SAFETY.md)); every contribution must keep it that way.

## Ground rules

1. Open an issue before large pull requests, and tag safety-relevant issues `safety-critical`.
2. All code needs type annotations, docstrings and tests, and must work on Python 3.10, 3.11 and
   3.12.
3. Never weaken a hard control in [SAFETY.md](SAFETY.md) without a linked `safety-critical`
   issue. The hard controls are the mandatory disclaimer, output validation, the ESCALATE gate, PII
   hashing, scope enforcement, dual-source drug validation and the hard timeouts.
4. Never add real patient data: fixtures must be synthetic, and identifiers in logs must be hashed.
5. Bug fixes ship with a regression test that fails before the fix.

## Before you open a pull request

Run the same checks as CI:

```bash
ruff check . && ruff format --check .
mypy src/medagent --ignore-missing-imports
pytest tests/ -v --tb=short --cov=src --cov-report=xml
```

Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`,
`chore:` …) and add a line to [CHANGELOG.md](CHANGELOG.md) under **Unreleased**.

## Adding a safety checker

1. Add the module under `src/medagent/safety/` with a `RESEARCH USE ONLY` rationale and no
   prescribing directives.
2. Add unit tests under `tests/unit/safety/`.
3. Document the control in [SAFETY.md](SAFETY.md). If it changes user-facing behaviour, also add a
   guide under `docs/guides/`.

## Safety panel entries

Per-panel entries (summary, safety number and demo GIF) belong in
[docs/SAFETY_PANEL_CATALOG.md](docs/SAFETY_PANEL_CATALOG.md), **not** in README.md. Append them under
*Entries added after the move*, and reference images as `../assets/<name>.gif` because the
catalog lives in `docs/`. The README is a concise overview: link to the catalog instead of adding
sections to it.
