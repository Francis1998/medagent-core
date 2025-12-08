# Usage Examples For Safety

*medagent-core — 2025-12-08*

## Overview

This guide covers usage examples for safety for the `medagent-core` project.

## Prerequisites

- Python 3.10+
- Redis (if using distributed mode)
- Environment variables configured (see `.env.example`)

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env

# Run the medagent module
python -m medagent --help
```

## Common Scenarios

### Scenario 1: Basic Safety Usage

```python
from medagent import Safety

client = Safety(config)
result = client.run()
print(result)
```

### Scenario 2: Advanced Configuration

```python
from medagent.config import Settings

settings = Settings(
    max_retries=3,
    timeout=30,
    log_level="INFO",
)
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `ConnectionError` | API endpoint unreachable | Check `BASE_URL` in `.env` |
| `TimeoutError` | Request took too long | Increase `timeout` setting |
| `AuthError` | Invalid or expired token | Rotate API key |

## See Also

- [README](../README.md)
- [ARCHITECTURE](../ARCHITECTURE.md)
- [API Reference](./API.md)
