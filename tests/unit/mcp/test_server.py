"""Protocol tests for the dual-era medagent MCP server (2026-07-28 + legacy)."""

from __future__ import annotations

import dataclasses
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import structlog
from structlog.testing import capture_logs

from medagent import __version__
from medagent.mcp import server as mcp_server
from medagent.mcp.server import SUPPORTED_PROTOCOL_VERSIONS, MedagentMcpServer, serve_stdio
from medagent.mcp.tools import ToolOutput
from medagent.safety.disclaimer import MANDATORY_DISCLAIMER
from medagent.safety.pii_hasher import hash_pii

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch

MODERN = "2026-07-28"
SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"


def modern_meta(version: str = MODERN) -> dict[str, Any]:
    """Per-request metadata a 2026-07-28 client sends on every request."""
    return {
        "io.modelcontextprotocol/protocolVersion": version,
        "io.modelcontextprotocol/clientCapabilities": {},
        "io.modelcontextprotocol/clientInfo": {"name": "pytest", "version": "1.0"},
    }


def rpc(method: str, params: dict[str, Any] | None = None, request_id: Any = 1) -> dict[str, Any]:
    """Build a JSON-RPC request."""
    message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    return message


def modern(
    method: str, params: dict[str, Any] | None = None, request_id: Any = 1
) -> dict[str, Any]:
    """Build a modern (stateless) request carrying the required ``_meta``."""
    return rpc(method, {**(params or {}), "_meta": modern_meta()}, request_id)


def call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Build a modern ``tools/call`` request."""
    return modern("tools/call", {"name": name, "arguments": arguments})


def initialize(server: MedagentMcpServer, version: str = "2025-11-25") -> dict[str, Any]:
    """Run the legacy handshake and return the initialize result."""
    response = server.handle_message(
        rpc(
            "initialize",
            {
                "protocolVersion": version,
                "capabilities": {},
                "clientInfo": {"name": "legacy-client", "version": "0.9"},
            },
        )
    )
    assert response is not None
    assert server.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    return response["result"]


@pytest.fixture()
def server() -> MedagentMcpServer:
    """A fresh server per test (the legacy handshake is process-scoped state)."""
    return MedagentMcpServer()


@pytest.fixture()
def server_logs(monkeypatch: MonkeyPatch) -> Any:
    """Capture structlog events emitted by ``medagent.mcp.server``."""
    with capture_logs() as logs:
        monkeypatch.setattr(mcp_server, "logger", structlog.get_logger(mcp_server.__name__))
        yield logs


# ---------------------------------------------------------------------------
# Modern era (2026-07-28)
# ---------------------------------------------------------------------------


def test_discover_advertises_versions_capabilities_and_identity(server: MedagentMcpServer) -> None:
    response = server.handle_message(modern("server/discover"))

    assert response is not None
    result = response["result"]
    assert response["id"] == 1
    assert result["resultType"] == "complete"
    assert result["supportedVersions"] == ["2026-07-28", "2025-11-25", "2025-06-18"]
    assert result["capabilities"] == {"tools": {}}
    assert result["_meta"][SERVER_INFO_KEY] == {
        "name": "medagent-core",
        "title": "medagent-core clinical safety tools",
        "version": __version__,
    }
    assert result["ttlMs"] > 0
    assert result["cacheScope"] == "public"
    assert "RESEARCH USE ONLY" in result["instructions"]


def test_modern_tools_list_is_cacheable_and_deterministic(server: MedagentMcpServer) -> None:
    first = server.handle_message(modern("tools/list"))
    second = server.handle_message(modern("tools/list", request_id="again"))

    assert first is not None and second is not None
    result = first["result"]
    names = [tool["name"] for tool in result["tools"]]
    assert names == [
        "check_drug_interactions",
        "list_safety_controls",
        "parse_fhir_bundle",
        "screen_medications",
    ]
    assert result["tools"] == second["result"]["tools"]
    assert result["resultType"] == "complete"
    assert result["ttlMs"] > 0
    assert result["cacheScope"] == "public"
    assert SERVER_INFO_KEY in result["_meta"]
    for tool in result["tools"]:
        assert tool["inputSchema"]["type"] == "object"
        assert tool["outputSchema"]["type"] == "object"
        assert tool["annotations"]["readOnlyHint"] is True
        assert tool["annotations"]["openWorldHint"] is False
        assert "RESEARCH USE ONLY" in tool["description"]


def test_modern_tool_call_returns_structured_and_text_content(server: MedagentMcpServer) -> None:
    response = server.handle_message(
        call("check_drug_interactions", {"medications": ["warfarin 5 mg", "ibuprofen 400 mg"]})
    )

    assert response is not None
    result = response["result"]
    assert result["resultType"] == "complete"
    assert result["isError"] is False
    assert SERVER_INFO_KEY in result["_meta"]
    structured = result["structuredContent"]
    assert "warfarin_nsaid" in {finding["check_id"] for finding in structured["findings"]}
    assert structured["disclaimer"] == MANDATORY_DISCLAIMER
    summary, serialized = result["content"]
    assert summary["type"] == serialized["type"] == "text"
    assert MANDATORY_DISCLAIMER in summary["text"]
    assert json.loads(serialized["text"]) == structured


def test_invalid_arguments_are_tool_errors_not_protocol_errors(server: MedagentMcpServer) -> None:
    response = server.handle_message(
        call("screen_medications", {"medications": [], "patient": {"name": "Jane Doe"}})
    )

    assert response is not None
    result = response["result"]
    assert result["isError"] is True
    assert "structuredContent" not in result
    text = result["content"][0]["text"]
    assert "arguments.medications must contain at least 1 item(s)" in text
    assert "arguments.patient.name is not an allowed property" in text
    assert MANDATORY_DISCLAIMER in text


def test_unknown_tool_is_a_protocol_error(server: MedagentMcpServer) -> None:
    response = server.handle_message(call("prescribe_drug", {}))

    assert response == {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": -32602, "message": "Unknown tool: prescribe_drug"},
    }


def test_unsupported_version_returns_32022_with_supported_list(server: MedagentMcpServer) -> None:
    request = rpc(
        "tools/list",
        {
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "1900-01-01",
                "io.modelcontextprotocol/clientCapabilities": {},
            }
        },
    )

    response = server.handle_message(request)

    assert response == {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {
            "code": -32022,
            "message": "Unsupported protocol version",
            "data": {"supported": list(SUPPORTED_PROTOCOL_VERSIONS), "requested": "1900-01-01"},
        },
    }


def test_missing_client_capabilities_is_invalid_params(server: MedagentMcpServer) -> None:
    request = rpc("tools/list", {"_meta": {"io.modelcontextprotocol/protocolVersion": MODERN}})

    response = server.handle_message(request)

    assert response is not None
    assert response["error"]["code"] == -32602
    assert "clientCapabilities" in response["error"]["message"]


def test_request_without_meta_before_initialize_is_rejected(server: MedagentMcpServer) -> None:
    response = server.handle_message(rpc("tools/list"))

    assert response is not None
    assert response["error"]["code"] == -32602
    assert response["error"]["data"] == {"supported": list(SUPPORTED_PROTOCOL_VERSIONS)}


@pytest.mark.parametrize("method", ["resources/list", "initialize", "ping", "logging/setLevel"])
def test_methods_outside_the_modern_surface_are_not_found(
    server: MedagentMcpServer, method: str
) -> None:
    response = server.handle_message(modern(method))

    assert response is not None
    assert response["error"]["code"] == -32601


@pytest.mark.parametrize(
    ("message", "fragment"),
    [
        (
            rpc("tools/list", {"_meta": {"io.modelcontextprotocol/protocolVersion": 20260728}}),
            "must be a string",
        ),
        (rpc("initialize", {"capabilities": {}}), "initialize requires a string protocolVersion"),
        (modern("tools/call", {"name": 7}), "tools/call requires a string name"),
        (
            modern("tools/call", {"name": "list_safety_controls", "arguments": ["x"]}),
            "arguments must be an object",
        ),
    ],
    ids=["numeric-version", "initialize-without-version", "non-string-name", "array-arguments"],
)
def test_malformed_params_are_invalid_params(
    server: MedagentMcpServer, message: dict[str, Any], fragment: str
) -> None:
    response = server.handle_message(message)

    assert response is not None
    assert response["error"]["code"] == -32602
    assert fragment in response["error"]["message"]


def test_scope_violation_is_reported_as_tool_error(server: MedagentMcpServer) -> None:
    response = server.handle_message(
        call("check_drug_interactions", {"medications": ["warfarin", "execute python now"]})
    )

    assert response is not None
    assert response["result"]["isError"] is True
    assert "scope enforcement" in response["result"]["content"][0]["text"]


def test_tools_list_rejects_unknown_cursor(server: MedagentMcpServer) -> None:
    response = server.handle_message(modern("tools/list", {"cursor": "page-2"}))

    assert response is not None
    assert response["error"]["code"] == -32602


# ---------------------------------------------------------------------------
# Legacy era (initialize handshake)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("version", ["2025-11-25", "2025-06-18"])
def test_legacy_initialize_negotiates_requested_version(
    server: MedagentMcpServer, version: str
) -> None:
    result = initialize(server, version)

    assert result["protocolVersion"] == version
    assert result["capabilities"] == {"tools": {"listChanged": False}}
    assert result["serverInfo"]["name"] == "medagent-core"
    assert "resultType" not in result


def test_legacy_initialize_with_unknown_version_offers_latest_legacy(
    server: MedagentMcpServer,
) -> None:
    assert initialize(server, "2024-11-05")["protocolVersion"] == "2025-11-25"


def test_legacy_session_results_have_legacy_shape(server: MedagentMcpServer) -> None:
    initialize(server, "2025-06-18")

    listed = server.handle_message(rpc("tools/list", request_id=2))
    called = server.handle_message(
        rpc(
            "tools/call",
            {"name": "check_drug_interactions", "arguments": {"medications": ["a", "b"]}},
            request_id=3,
        )
    )
    pinged = server.handle_message(rpc("ping", request_id=4))

    assert listed is not None and called is not None
    assert set(listed["result"]) == {"tools"}
    assert set(called["result"]) == {"content", "structuredContent", "isError"}
    assert pinged == {"jsonrpc": "2.0", "id": 4, "result": {}}


def test_legacy_version_in_meta_is_served_with_legacy_shape(server: MedagentMcpServer) -> None:
    response = server.handle_message(
        rpc("tools/list", {"_meta": {"io.modelcontextprotocol/protocolVersion": "2025-11-25"}})
    )

    assert response is not None
    assert set(response["result"]) == {"tools"}


def test_dual_era_process_still_serves_modern_requests(server: MedagentMcpServer) -> None:
    initialize(server)

    response = server.handle_message(modern("server/discover", request_id=9))

    assert response is not None
    assert response["result"]["resultType"] == "complete"


# ---------------------------------------------------------------------------
# JSON-RPC framing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        '{"jsonrpc": "2.0", "id": 1,',
        b"\xff\xfe not utf-8",
        "[" * 100_000,
        '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"x": NaN}}',
    ],
    ids=["truncated", "invalid-utf8", "deeply-nested", "nan-literal"],
)
def test_malformed_lines_return_parse_error_without_id(
    server: MedagentMcpServer, line: str | bytes
) -> None:
    assert server.handle_line(line) == {
        "jsonrpc": "2.0",
        "error": {"code": -32700, "message": "Parse error"},
    }


def test_internal_errors_are_reported_without_leaking_details(
    server: MedagentMcpServer, monkeypatch: MonkeyPatch, server_logs: list[dict[str, Any]]
) -> None:
    def explode(arguments: dict[str, Any]) -> ToolOutput:
        raise RuntimeError("CANARY warfarin 5 mg for MRN-0042")

    tool = mcp_server.TOOLS_BY_NAME["list_safety_controls"]
    broken = dataclasses.replace(tool, handler=explode)
    monkeypatch.setitem(mcp_server.TOOLS_BY_NAME, "list_safety_controls", broken)

    response = server.handle_message(call("list_safety_controls", {}))

    assert response == {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": -32603, "message": "Internal error"},
    }
    assert "CANARY" not in repr(server_logs)
    failure = next(entry for entry in server_logs if entry["event"] == "mcp_internal_error")
    assert failure["error_type"] == "RuntimeError"
    assert failure["where"].startswith("test_server.py:")


@pytest.mark.parametrize(
    "message",
    [
        [{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}],
        "tools/list",
        {"jsonrpc": "1.0", "id": 1, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 1, "method": 7},
        {"jsonrpc": "2.0", "id": True, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": None, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": ["x"]},
        {"jsonrpc": "2.0", "id": 1},
    ],
    ids=[
        "batch",
        "not-object",
        "wrong-version",
        "non-string-method",
        "bool-id",
        "null-id",
        "array-params",
        "no-method",
    ],
)
def test_invalid_requests_return_invalid_request(server: MedagentMcpServer, message: Any) -> None:
    response = server.handle_message(message)

    assert response is not None
    assert response["error"]["code"] == -32600


@pytest.mark.parametrize(
    "message",
    [
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}},
        {"jsonrpc": "2.0", "method": "notifications/unknown"},
        {"jsonrpc": "2.0", "method": "tools/list", "params": ["bad"]},
        {"jsonrpc": "2.0", "id": 5, "result": {}},
    ],
    ids=["initialized", "cancelled", "unknown-notification", "bad-notification", "response"],
)
def test_notifications_and_responses_never_get_replies(
    server: MedagentMcpServer, message: dict[str, Any]
) -> None:
    assert server.handle_message(message) is None


# ---------------------------------------------------------------------------
# Safety guard and audit log
# ---------------------------------------------------------------------------


def test_prescription_language_in_tool_output_is_withheld(
    server: MedagentMcpServer, monkeypatch: MonkeyPatch
) -> None:
    tool = mcp_server.TOOLS_BY_NAME["list_safety_controls"]
    unsafe = dataclasses.replace(
        tool, handler=lambda arguments: ToolOutput({"advice": "x"}, "Prescribe 5 mg daily.")
    )
    monkeypatch.setitem(mcp_server.TOOLS_BY_NAME, "list_safety_controls", unsafe)

    response = server.handle_message(call("list_safety_controls", {}))

    assert response is not None
    result = response["result"]
    assert result["isError"] is True
    assert "structuredContent" not in result
    assert result["content"][0]["text"].startswith("Result withheld")
    assert "Prescribe" not in result["content"][0]["text"]


@pytest.mark.parametrize(
    "structured",
    [
        {"note": "administer\n5 mg now"},
        {"nested": [{"text": "start the patient on\twarfarin"}]},
        {"administer\t5 mg": 1},
    ],
    ids=["newline-in-value", "tab-in-nested-value", "directive-in-key"],
)
def test_output_guard_scans_raw_strings_and_keys(
    server: MedagentMcpServer, monkeypatch: MonkeyPatch, structured: dict[str, Any]
) -> None:
    tool = mcp_server.TOOLS_BY_NAME["list_safety_controls"]
    unsafe = dataclasses.replace(
        tool, handler=lambda arguments: ToolOutput(structured, "summary only")
    )
    monkeypatch.setitem(mcp_server.TOOLS_BY_NAME, "list_safety_controls", unsafe)

    response = server.handle_message(call("list_safety_controls", {}))

    assert response is not None
    assert response["result"]["isError"] is True
    assert response["result"]["content"][0]["text"].startswith("Result withheld")


def test_audit_log_keeps_only_bounded_client_identity(tmp_path: Path) -> None:
    audit_path = tmp_path / "mcp.jsonl"
    server = MedagentMcpServer(audit_log_path=audit_path)
    request = call("list_safety_controls", {"category": "platform"})
    request["params"]["_meta"]["io.modelcontextprotocol/clientInfo"] = {
        "name": "ehr-agent call 415-555-0101",
        "version": "9" * 200,
        "mrn": "MRN-0042",
        "bundle": {"resourceType": "Bundle"},
    }

    server.handle_message(request)

    raw = audit_path.read_text(encoding="utf-8")
    record = json.loads(raw)
    assert set(record["client"]) == {"name", "version"}
    assert record["client"]["version"] == "9" * 64
    for leaked in ("MRN-0042", "Bundle", "415-555-0101"):
        assert leaked not in raw


def test_internal_errors_are_recorded_in_the_audit_log(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    def explode(arguments: dict[str, Any]) -> ToolOutput:
        raise RuntimeError("CANARY boom")

    tool = mcp_server.TOOLS_BY_NAME["list_safety_controls"]
    monkeypatch.setitem(
        mcp_server.TOOLS_BY_NAME,
        "list_safety_controls",
        dataclasses.replace(tool, handler=explode),
    )
    audit_path = tmp_path / "mcp.jsonl"
    server = MedagentMcpServer(audit_log_path=audit_path)

    response = server.handle_message(call("list_safety_controls", {}))

    assert response is not None
    assert response["error"]["code"] == -32603
    record = json.loads(audit_path.read_text(encoding="utf-8"))
    assert record["error_kind"] == "internal_error"
    assert record["is_error"] is True
    assert "CANARY" not in json.dumps(record)


def test_audit_log_records_hashes_and_counts_never_arguments(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit" / "mcp.jsonl"
    server = MedagentMcpServer(audit_log_path=audit_path)
    arguments = {
        "medications": ["warfarin 5 mg", "ibuprofen 400 mg"],
        "patient": {"age": 81},
        "patient_ref": "MRN-0042",
    }

    response = server.handle_message(call("screen_medications", arguments))
    server.handle_message(call("screen_medications", {"medications": []}))

    assert response is not None
    assert "MRN-0042" not in json.dumps(response)
    raw = audit_path.read_text(encoding="utf-8")
    assert "MRN-0042" not in raw
    assert "warfarin" not in raw
    ok, failed = (json.loads(line) for line in raw.splitlines())
    canonical = json.dumps(arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert ok["tool"] == "screen_medications"
    assert ok["era"] == "modern"
    assert ok["protocol_version"] == MODERN
    assert ok["client"] == {"name": "pytest", "version": "1.0"}
    assert ok["inputs_hash"] == hash_pii(canonical)
    assert ok["patient_ref_hash"] == hash_pii("MRN-0042")
    assert ok["is_error"] is False
    assert ok["finding_count"] == response["result"]["structuredContent"]["finding_count"]
    assert failed["is_error"] is True
    assert failed["error_kind"] == "invalid_arguments"


def test_audit_log_write_failure_does_not_break_tool_calls(tmp_path: Path) -> None:
    server = MedagentMcpServer(audit_log_path=tmp_path)

    response = server.handle_message(call("list_safety_controls", {"category": "platform"}))

    assert response is not None
    assert response["result"]["isError"] is False


# ---------------------------------------------------------------------------
# stdio transport
# ---------------------------------------------------------------------------


def test_serve_stdio_skips_blank_lines_and_rejects_oversized_messages(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(mcp_server, "MAX_MESSAGE_BYTES", 512)
    oversized = json.dumps(modern("tools/list", {"pad": "x" * 1200})).encode()
    stdin = io.BytesIO(
        b"\n" + oversized + b"\n" + json.dumps(modern("server/discover")).encode() + b"\n"
    )
    stdout = io.BytesIO()

    serve_stdio(MedagentMcpServer(), stdin, stdout)

    first, second = (json.loads(line) for line in stdout.getvalue().splitlines())
    assert first["error"] == {"code": -32600, "message": "Message exceeds 512 bytes"}
    assert second["result"]["resultType"] == "complete"


def test_lone_surrogate_request_id_does_not_end_the_stdio_session() -> None:
    bad_id = b'{"jsonrpc":"2.0","id":"\\ud800","method":"ping"}'
    stdin = io.BytesIO(bad_id + b"\n" + json.dumps(modern("server/discover")).encode() + b"\n")
    stdout = io.BytesIO()

    serve_stdio(MedagentMcpServer(), stdin, stdout)

    first, second = (json.loads(line) for line in stdout.getvalue().splitlines())
    assert first["id"] == "\ud800"
    assert second["result"]["resultType"] == "complete"
    assert stdout.getvalue().isascii()


def test_stdio_subprocess_round_trip_for_both_eras() -> None:
    meta = modern_meta()
    messages = [
        rpc("server/discover", {"_meta": meta}, 1),
        rpc("tools/list", {"_meta": meta}, 2),
        rpc(
            "tools/call",
            {
                "name": "screen_medications",
                "arguments": {
                    "medications": ["warfarin 5 mg", "ibuprofen 400 mg"],
                    "patient": {"age": 79, "egfr": 25},
                },
                "_meta": meta,
            },
            3,
        ),
        rpc(
            "initialize",
            {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "x"}},
            4,
        ),
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        rpc("tools/call", {"name": "list_safety_controls", "arguments": {"query": "qt"}}, 5),
    ]
    payload = "".join(json.dumps(message) + "\n" for message in messages)

    completed = subprocess.run(
        [sys.executable, "-m", "medagent.mcp"],
        input=payload.encode(),
        capture_output=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr.decode()
    responses = [json.loads(line) for line in completed.stdout.decode().splitlines()]
    assert [response["id"] for response in responses] == [1, 2, 3, 4, 5]
    assert all(response["jsonrpc"] == "2.0" and "result" in response for response in responses)
    discover, listed, screened, initialized, legacy_call = (r["result"] for r in responses)
    assert discover["supportedVersions"][0] == MODERN
    assert len(listed["tools"]) == 4
    assert screened["structuredContent"]["escalation_recommended"] is True
    assert initialized["protocolVersion"] == "2025-06-18"
    assert "resultType" not in legacy_call
    assert legacy_call["structuredContent"]["count"] > 0


def test_invalid_log_level_is_rejected_by_the_cli() -> None:
    with pytest.raises(SystemExit) as exc_info:
        mcp_server.main(["--log-level", "LOUD"])

    assert exc_info.value.code == 2


def test_module_entry_point_reports_version() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "medagent.mcp", "--version"],
        capture_output=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stdout.decode().strip() == (
        f"medagent-mcp {__version__} (MCP 2026-07-28, 2025-11-25, 2025-06-18)"
    )
