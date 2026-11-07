"""Model Context Protocol (MCP) server for medagent's deterministic safety tools.

Exposes offline medication-safety screening, offline drug-interaction rules,
FHIR R4 Bundle normalisation and the safety-control catalogue to MCP hosts
(Claude Desktop, Claude Code, Cursor, VS Code) over stdio. The server is
dependency-free (stdlib JSON-RPC) and dual-era: stateless ``2026-07-28``
requests and legacy ``initialize`` clients (``2025-11-25`` / ``2025-06-18``).

RESEARCH USE ONLY. Not FDA-cleared.
"""

from medagent.mcp.server import (
    LEGACY_PROTOCOL_VERSIONS,
    MODERN_PROTOCOL_VERSIONS,
    SUPPORTED_PROTOCOL_VERSIONS,
    MedagentMcpServer,
    main,
    serve_stdio,
)

__all__ = [
    "LEGACY_PROTOCOL_VERSIONS",
    "MODERN_PROTOCOL_VERSIONS",
    "SUPPORTED_PROTOCOL_VERSIONS",
    "MedagentMcpServer",
    "main",
    "serve_stdio",
]
