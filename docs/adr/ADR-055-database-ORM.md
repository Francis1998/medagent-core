# ADR-055: Database Orm for medagent-core

**Date:** 2025-11-12
**Status:** Accepted
**Context:** Biomedical Ai

## Context

The `medagent` module needs a reliable database ORM solution
that integrates cleanly with our async clinical pipeline.

## Decision

Use **SQLAlchemy 2.0** for database ORM.

## Considered Alternatives

| Option | Pros | Cons |
|--------|------|------|
| **SQLAlchemy 2.0** (chosen) | Native async, well-maintained | Slightly higher cold-start |
| Tortoise ORM | Mature ecosystem | Sync-first, harder to integrate |
| raw SQL | Zero dependencies | Limited features for production |

## Consequences

- All new clinical components will use `SQLAlchemy 2.0` as the database ORM layer.
- Existing code will be migrated incrementally.
- Added to `pyproject.toml` as a core dependency.
