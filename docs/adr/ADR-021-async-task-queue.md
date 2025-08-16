# ADR-021: Async Task Queue for medagent-core

**Date:** 2025-08-16
**Status:** Accepted
**Context:** Biomedical Ai

## Context

The `medagent` module needs a reliable async task queue solution
that integrates cleanly with our async safety pipeline.

## Decision

Use **Redis Streams** for async task queue.

## Considered Alternatives

| Option | Pros | Cons |
|--------|------|------|
| **Redis Streams** (chosen) | Native async, well-maintained | Slightly higher cold-start |
| Celery + RabbitMQ | Mature ecosystem | Sync-first, harder to integrate |
| asyncio.Queue | Zero dependencies | Limited features for production |

## Consequences

- All new safety components will use `Redis Streams` as the async task queue layer.
- Existing code will be migrated incrementally.
- Added to `pyproject.toml` as a core dependency.
