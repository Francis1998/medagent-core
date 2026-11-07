"""Dual-era MCP stdio server for medagent's deterministic safety tools.

Speaks newline-delimited JSON-RPC 2.0 over stdin/stdout with only the Python
standard library:

* **Modern** (``2026-07-28``): stateless. Every request carries
  ``_meta["io.modelcontextprotocol/protocolVersion"]`` and
  ``_meta["io.modelcontextprotocol/clientCapabilities"]``; ``server/discover``
  advertises versions, capabilities and identity; every result carries
  ``resultType`` and ``_meta["io.modelcontextprotocol/serverInfo"]``.
* **Legacy** (``2025-11-25``, ``2025-06-18``): the ``initialize`` handshake
  selects legacy semantics for the stdio process.

STDOUT carries protocol messages only; logs go to STDERR. Tool calls can be
appended to a JSONL audit file that holds hashes and counts, never arguments.
RESEARCH USE ONLY.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

from medagent import __version__
from medagent.config import settings
from medagent.llm.validator import MedicalOutputValidationError, MedicalOutputValidator
from medagent.logging_config import configure_logging, get_logger
from medagent.mcp.schema import validate
from medagent.mcp.tools import TOOLS, TOOLS_BY_NAME, ToolInputError, ToolOutput, ToolSpec
from medagent.safety.disclaimer import MANDATORY_DISCLAIMER
from medagent.safety.pii_hasher import hash_pii

logger = get_logger(__name__)

MODERN_PROTOCOL_VERSIONS: tuple[str, ...] = ("2026-07-28",)
LEGACY_PROTOCOL_VERSIONS: tuple[str, ...] = ("2025-11-25", "2025-06-18")
SUPPORTED_PROTOCOL_VERSIONS: tuple[str, ...] = MODERN_PROTOCOL_VERSIONS + LEGACY_PROTOCOL_VERSIONS

META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CLIENT_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
META_CLIENT_INFO = "io.modelcontextprotocol/clientInfo"
META_SERVER_INFO = "io.modelcontextprotocol/serverInfo"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
UNSUPPORTED_PROTOCOL_VERSION = -32022

CACHE_TTL_MS = 3_600_000
MAX_MESSAGE_BYTES = 8 * 1024 * 1024
AUDIT_LOG_ENV = "MEDAGENT_MCP_AUDIT_LOG"
LOG_LEVEL_ENV = "MEDAGENT_MCP_LOG_LEVEL"
_DEFAULT_PII_SALT = "insecure-default-change-me"

SERVER_INFO: dict[str, str] = {
    "name": "medagent-core",
    "title": "medagent-core clinical safety tools",
    "version": __version__,
}

SERVER_INSTRUCTIONS = (
    "medagent-core exposes deterministic, offline medication-safety tools for RESEARCH USE "
    "ONLY. Typical flow: parse_fhir_bundle, then screen_medications with its "
    "screening_input; use check_drug_interactions for a quick interaction-only pass and "
    "list_safety_controls to explain coverage. Findings are advisory for clinician review: "
    "never present them as prescriptions or treatment orders, and never treat an empty "
    "result as evidence of safety."
)

_LEGACY_METHODS = frozenset({"initialize", "ping", "tools/list", "tools/call"})
_MODERN_METHODS = frozenset({"server/discover", "tools/list", "tools/call"})


class McpError(Exception):
    """A JSON-RPC error returned to the client instead of a result."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

    def to_error(self) -> dict[str, Any]:
        """Return the JSON-RPC ``error`` member."""
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            error["data"] = self.data
        return error


class ToolCallAuditLog:
    """Append-only JSONL record of tool calls (hashes and counts only)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def record(self, entry: dict[str, Any]) -> None:
        """Append one entry; failures are logged and never break the tool call."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        except OSError as exc:
            logger.error("mcp_audit_write_failed", error_type=type(exc).__name__)


def _canonical_json(value: Any) -> str:
    """Serialise ``value`` deterministically for hashing."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _reject_json_constant(name: str) -> Any:
    """Reject the non-standard ``NaN``/``Infinity`` literals Python's json accepts."""
    raise ValueError(f"Non-standard JSON constant: {name}")


def _encode(message: dict[str, Any]) -> bytes:
    """Encode one JSON-RPC message as a single, strictly valid UTF-8 JSON line."""
    text = json.dumps(message, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return text.encode("utf-8") + b"\n"


class MedagentMcpServer:
    """Transport-independent MCP dispatcher for medagent's safety tools.

    Args:
        audit_log_path: Optional JSONL file that receives one record per
            ``tools/call`` (tool name, era, hashes, counts, timing).
    """

    def __init__(self, audit_log_path: Path | None = None) -> None:
        self._audit_log = ToolCallAuditLog(audit_log_path) if audit_log_path else None
        self._output_guard = MedicalOutputValidator()
        self._legacy_version: str | None = None
        self._legacy_client: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Message entry points
    # ------------------------------------------------------------------

    def handle_line(self, line: str | bytes) -> dict[str, Any] | None:
        """Handle one newline-delimited message; return the response, if any."""
        try:
            message = json.loads(line, parse_constant=_reject_json_constant)
        except (ValueError, RecursionError):
            return self._error(None, PARSE_ERROR, "Parse error")
        return self.handle_message(message)

    def handle_message(self, message: Any) -> dict[str, Any] | None:
        """Handle one decoded JSON-RPC message; return the response, if any."""
        if isinstance(message, list):
            return self._error(None, INVALID_REQUEST, "Batch requests are not supported")
        if not isinstance(message, dict):
            return self._error(None, INVALID_REQUEST, "Message must be a JSON object")
        if "method" not in message:
            if "id" in message and ("result" in message or "error" in message):
                return None  # A response to a request this server never sends.
            return self._error(None, INVALID_REQUEST, "Missing method")

        if "id" not in message:
            # Notifications never get a response; requests run synchronously, so
            # notifications/initialized and notifications/cancelled need no action.
            return None
        request_id = message["id"]
        if isinstance(request_id, bool) or not isinstance(request_id, (str, int)):
            return self._error(None, INVALID_REQUEST, "Request id must be a string or integer")
        method = message["method"]
        params = message.get("params", {})
        if message.get("jsonrpc") != "2.0" or not isinstance(method, str):
            return self._error(request_id, INVALID_REQUEST, "Invalid Request")
        if not isinstance(params, dict):
            return self._error(request_id, INVALID_REQUEST, "params must be an object")

        try:
            era, version = self._resolve_era(method, params)
            result = self._dispatch(method, params, era, version)
        except McpError as exc:
            return self._error(request_id, exc.code, exc.message, exc.data)
        except Exception as exc:
            # Never log the message or traceback text: it can echo clinical input.
            frame = traceback.extract_tb(exc.__traceback__)[-1]
            logger.error(
                "mcp_internal_error",
                method=method,
                error_type=type(exc).__name__,
                where=f"{Path(frame.filename).name}:{frame.lineno}",
            )
            return self._error(request_id, INTERNAL_ERROR, "Internal error")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    # ------------------------------------------------------------------
    # Era / version negotiation
    # ------------------------------------------------------------------

    def _resolve_era(self, method: str, params: dict[str, Any]) -> tuple[str, str]:
        """Return ("modern" | "legacy", protocol version) for one request."""
        raw_meta = params.get("_meta")
        meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
        version = meta.get(META_PROTOCOL_VERSION)
        if version is not None:
            if not isinstance(version, str):
                raise McpError(INVALID_PARAMS, f"_meta['{META_PROTOCOL_VERSION}'] must be a string")
            if version in MODERN_PROTOCOL_VERSIONS:
                if not isinstance(meta.get(META_CLIENT_CAPABILITIES), dict):
                    raise McpError(
                        INVALID_PARAMS,
                        f"Missing required _meta field '{META_CLIENT_CAPABILITIES}'",
                    )
                return "modern", version
            if version in LEGACY_PROTOCOL_VERSIONS:
                return "legacy", version
            raise McpError(
                UNSUPPORTED_PROTOCOL_VERSION,
                "Unsupported protocol version",
                {"supported": list(SUPPORTED_PROTOCOL_VERSIONS), "requested": version},
            )
        if method in {"initialize", "ping"} or method.startswith("notifications/"):
            return "legacy", self._legacy_version or LEGACY_PROTOCOL_VERSIONS[0]
        if self._legacy_version is not None:
            return "legacy", self._legacy_version
        raise McpError(
            INVALID_PARAMS,
            f"Missing required _meta field '{META_PROTOCOL_VERSION}'. Clients on "
            f"{MODERN_PROTOCOL_VERSIONS[0]} must send it on every request; legacy clients "
            "must call initialize first.",
            {"supported": list(SUPPORTED_PROTOCOL_VERSIONS)},
        )

    # ------------------------------------------------------------------
    # Method dispatch
    # ------------------------------------------------------------------

    def _dispatch(
        self, method: str, params: dict[str, Any], era: str, version: str
    ) -> dict[str, Any]:
        """Route a request to its handler and shape the result for its era."""
        allowed = _MODERN_METHODS if era == "modern" else _LEGACY_METHODS
        if method not in allowed:
            raise McpError(METHOD_NOT_FOUND, f"Method not found: {method} (protocol {version})")
        if method == "initialize":
            return self._initialize(params)
        if method == "ping":
            return {}
        if method == "server/discover":
            result: dict[str, Any] = {
                "supportedVersions": list(SUPPORTED_PROTOCOL_VERSIONS),
                "capabilities": {"tools": {}},
                "instructions": SERVER_INSTRUCTIONS,
                "ttlMs": CACHE_TTL_MS,
                "cacheScope": "public",
            }
        elif method == "tools/list":
            if params.get("cursor") is not None:
                raise McpError(INVALID_PARAMS, "Invalid cursor: tools/list is not paginated")
            result = {"tools": [tool.definition() for tool in TOOLS]}
            if era == "modern":
                result.update({"ttlMs": CACHE_TTL_MS, "cacheScope": "public"})
        else:
            result = self._call_tool(params, era, version)
        if era == "modern":
            result = {"resultType": "complete", **result, "_meta": {META_SERVER_INFO: SERVER_INFO}}
        return result

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Legacy handshake: negotiate a legacy version for this stdio process."""
        requested = params.get("protocolVersion")
        if not isinstance(requested, str):
            raise McpError(INVALID_PARAMS, "initialize requires a string protocolVersion")
        negotiated = (
            requested if requested in LEGACY_PROTOCOL_VERSIONS else LEGACY_PROTOCOL_VERSIONS[0]
        )
        self._legacy_version = negotiated
        client_info = params.get("clientInfo")
        self._legacy_client = client_info if isinstance(client_info, dict) else None
        logger.info("mcp_legacy_session", requested=requested, negotiated=negotiated)
        return {
            "protocolVersion": negotiated,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": SERVER_INSTRUCTIONS,
        }

    def _call_tool(self, params: dict[str, Any], era: str, version: str) -> dict[str, Any]:
        """Run ``tools/call``: protocol errors raise, tool errors return ``isError``."""
        name = params.get("name")
        if not isinstance(name, str):
            raise McpError(INVALID_PARAMS, "tools/call requires a string name")
        tool = TOOLS_BY_NAME.get(name)
        if tool is None:
            raise McpError(INVALID_PARAMS, f"Unknown tool: {name}")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            raise McpError(INVALID_PARAMS, "tools/call arguments must be an object")

        started = time.perf_counter()
        error_kind: str | None = None
        output: ToolOutput | None = None
        problems = validate(arguments, tool.input_schema)
        if problems:
            error_kind, message = "invalid_arguments", "Invalid arguments: " + "; ".join(problems)
        else:
            try:
                output = tool.handler(arguments)
                error_kind, message = self._guard_output(tool, output)
            except ToolInputError as exc:
                error_kind, message = "invalid_arguments", str(exc)

        if output is None or error_kind is not None:
            result: dict[str, Any] = {
                "content": [{"type": "text", "text": f"{message}\n{MANDATORY_DISCLAIMER}"}],
                "isError": True,
            }
        else:
            result = {
                "content": [
                    {"type": "text", "text": output.summary},
                    {"type": "text", "text": json.dumps(output.structured, ensure_ascii=False)},
                ],
                "structuredContent": output.structured,
                "isError": False,
            }
        self._record_call(tool, arguments, output, error_kind, era, version, params, started)
        return result

    def _guard_output(self, tool: ToolSpec, output: ToolOutput) -> tuple[str | None, str]:
        """Withhold any result containing prescription language (SAFETY.md §3.3)."""
        try:
            self._output_guard.check_prohibited_language(output.summary)
            self._output_guard.check_prohibited_language(_canonical_json(output.structured))
        except MedicalOutputValidationError:
            logger.error("mcp_output_withheld", tool=tool.name)
            return (
                "output_withheld",
                "Result withheld: it matched prohibited prescription language (SAFETY.md §3.3). "
                "Escalate to a licensed clinician.",
            )
        return None, ""

    def _record_call(
        self,
        tool: ToolSpec,
        arguments: dict[str, Any],
        output: ToolOutput | None,
        error_kind: str | None,
        era: str,
        version: str,
        params: dict[str, Any],
        started: float,
    ) -> None:
        """Log a tool call to STDERR and, when configured, the JSONL audit file."""
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        structured = output.structured if output is not None and error_kind is None else {}
        patient_ref = arguments.get("patient_ref")
        patient_ref_hash = hash_pii(patient_ref) if isinstance(patient_ref, str) else None
        meta = params.get("_meta")
        client = meta.get(META_CLIENT_INFO) if isinstance(meta, dict) else self._legacy_client
        logger.info(
            "mcp_tool_call",
            tool=tool.name,
            era=era,
            is_error=error_kind is not None,
            duration_ms=duration_ms,
            finding_count=structured.get("finding_count"),
        )
        if self._audit_log is None:
            return
        self._audit_log.record(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "event": "mcp_tool_call",
                "tool": tool.name,
                "era": era,
                "protocol_version": version,
                "client": client if isinstance(client, dict) else None,
                "is_error": error_kind is not None,
                "error_kind": error_kind,
                "duration_ms": duration_ms,
                "inputs_hash": hash_pii(_canonical_json(arguments)),
                "patient_ref_hash": patient_ref_hash,
                "patient_id_hash": structured.get("patient_id_hash"),
                "finding_count": structured.get("finding_count"),
                "highest_severity": structured.get("highest_severity"),
            }
        )

    @staticmethod
    def _error(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
        """Build a JSON-RPC error response (``id`` omitted when it is unknown)."""
        response: dict[str, Any] = {"jsonrpc": "2.0"}
        if request_id is not None:
            response["id"] = request_id
        response["error"] = McpError(code, message, data).to_error()
        return response


def _read_message(stream: IO[bytes]) -> bytes | None:
    """Read one line, discarding (and flagging) lines over ``MAX_MESSAGE_BYTES``."""
    line = stream.readline(MAX_MESSAGE_BYTES + 1)
    if not line:
        return None
    if len(line) > MAX_MESSAGE_BYTES and not line.endswith(b"\n"):
        while True:
            rest = stream.readline(MAX_MESSAGE_BYTES)
            if not rest or rest.endswith(b"\n"):
                break
        return b""
    return line


def serve_stdio(server: MedagentMcpServer, stdin: IO[bytes], stdout: IO[bytes]) -> None:
    """Serve newline-delimited JSON-RPC until ``stdin`` reaches end-of-file."""
    while True:
        line = _read_message(stdin)
        if line is None:
            return
        response: dict[str, Any] | None
        if line == b"":
            response = MedagentMcpServer._error(
                None, INVALID_REQUEST, f"Message exceeds {MAX_MESSAGE_BYTES} bytes"
            )
        elif not line.strip():
            continue
        else:
            response = server.handle_line(line)
        if response is None:
            continue
        try:
            payload = _encode(response)
        except ValueError:
            logger.error("mcp_unencodable_response")
            payload = _encode(
                MedagentMcpServer._error(response.get("id"), INTERNAL_ERROR, "Internal error")
            )
        stdout.write(payload)
        stdout.flush()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the MCP server on stdio (``medagent-mcp`` / ``python -m medagent.mcp``)."""
    parser = argparse.ArgumentParser(
        prog="medagent-mcp",
        description=(
            "Dual-era MCP stdio server for medagent's deterministic safety tools. "
            "RESEARCH USE ONLY."
        ),
    )
    parser.add_argument(
        "--audit-log",
        type=Path,
        default=os.environ.get(AUDIT_LOG_ENV) or None,
        help=f"Append one JSONL record per tool call to this file (env: {AUDIT_LOG_ENV}).",
    )
    parser.add_argument(
        "--log-level",
        type=str.upper,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=os.environ.get(LOG_LEVEL_ENV, "WARNING").upper(),
        help=f"STDERR log level (env: {LOG_LEVEL_ENV}; default WARNING).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"medagent-mcp {__version__} (MCP {', '.join(SUPPORTED_PROTOCOL_VERSIONS)})",
    )
    args = parser.parse_args(argv)

    protocol_out = sys.stdout.buffer
    sys.stdout = sys.stderr  # Stray prints must never corrupt the protocol stream.
    configure_logging(args.log_level)
    if settings.pii_hash_salt == _DEFAULT_PII_SALT:
        logger.warning(
            "pii_hash_salt_default",
            message="Set PII_HASH_SALT so hashed identifiers are not guessable.",
        )
    server = MedagentMcpServer(audit_log_path=args.audit_log)
    logger.info(
        "mcp_server_started",
        versions=list(SUPPORTED_PROTOCOL_VERSIONS),
        audit_log=str(args.audit_log) if args.audit_log else None,
    )
    try:
        serve_stdio(server, sys.stdin.buffer, protocol_out)
    except (KeyboardInterrupt, BrokenPipeError):
        pass
    return 0
