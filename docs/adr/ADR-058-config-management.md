# ADR-058: Config Management for medagent-core

**Date:** 2025-03-03
**Status:** Accepted
**Context:** Biomedical Ai

## Context

The `medagent` module needs a reliable config management solution
that integrates cleanly with our async health pipeline.

## Decision

Use **pydantic-settings** for config management.

## Considered Alternatives

| Option | Pros | Cons |
|--------|------|------|
| **pydantic-settings** (chosen) | Native async, well-maintained | Slightly higher cold-start |
| dynaconf | Mature ecosystem | Sync-first, harder to integrate |
| raw os.environ | Zero dependencies | Limited features for production |

## Consequences

- All new health components will use `pydantic-settings` as the config management layer.
- Existing code will be migrated incrementally.
- Added to `pyproject.toml` as a core dependency.
