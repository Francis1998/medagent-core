# ADR-014: Http Client for medagent-core

**Date:** 2026-05-06
**Status:** Accepted
**Context:** Biomedical Ai

## Context

The `medagent` module needs a reliable HTTP client solution
that integrates cleanly with our async reasoning pipeline.

## Decision

Use **httpx (async)** for HTTP client.

## Considered Alternatives

| Option | Pros | Cons |
|--------|------|------|
| **httpx (async)** (chosen) | Native async, well-maintained | Slightly higher cold-start |
| aiohttp | Mature ecosystem | Sync-first, harder to integrate |
| requests | Zero dependencies | Limited features for production |

## Consequences

- All new reasoning components will use `httpx (async)` as the HTTP client layer.
- Existing code will be migrated incrementally.
- Added to `pyproject.toml` as a core dependency.
