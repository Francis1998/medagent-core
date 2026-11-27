"""MCP tests for ``list_calculators`` and ``run_calculator`` across both protocol eras."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from medagent.mcp.schema import validate
from medagent.mcp.server import MedagentMcpServer
from medagent.mcp.tools import TOOLS_BY_NAME
from medagent.safety.disclaimer import MANDATORY_DISCLAIMER

MODERN_META: dict[str, Any] = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientCapabilities": {},
    "io.modelcontextprotocol/clientInfo": {"name": "pytest", "version": "1.0"},
}
CURB65 = {
    "confusion": True,
    "urea": {"value": 26, "unit": "mg/dL"},
    "respiratory_rate": 32,
    "systolic_bp": 88,
    "diastolic_bp": 58,
    "age": 72,
}


def _legacy_server(**kwargs: Any) -> MedagentMcpServer:
    server = MedagentMcpServer(**kwargs)
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {}},
        }
    )
    return server


def _call(
    server: MedagentMcpServer, name: str, arguments: Any, *, modern: bool = True
) -> dict[str, Any]:
    params: dict[str, Any] = {"name": name, "arguments": arguments}
    if modern:
        params["_meta"] = MODERN_META
    response = server.handle_message(
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": params}
    )
    assert response is not None and "result" in response, response
    return dict(response["result"])


def test_both_tools_are_listed_read_only_in_both_eras() -> None:
    modern = MedagentMcpServer().handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"_meta": MODERN_META}}
    )
    legacy = _legacy_server().handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert modern is not None and legacy is not None
    for listed in (modern["result"]["tools"], legacy["result"]["tools"]):
        tools = {tool["name"]: tool for tool in listed}
        assert tools["run_calculator"]["inputSchema"]["required"] == ["calculator_id", "inputs"]
        assert (
            "curb_65"
            in tools["run_calculator"]["inputSchema"]["properties"]["calculator_id"]["enum"]
        )
        for name in ("list_calculators", "run_calculator"):
            assert tools[name]["annotations"]["readOnlyHint"] is True
            assert tools[name]["outputSchema"]["properties"]["disclaimer"]["const"] == (
                MANDATORY_DISCLAIMER
            )


@pytest.mark.parametrize("modern", [True, False])
def test_run_calculator_returns_structured_derivations(modern: bool) -> None:
    server = MedagentMcpServer() if modern else _legacy_server()
    result = _call(
        server, "run_calculator", {"calculator_id": "curb_65", "inputs": CURB65}, modern=modern
    )
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert validate(structured, TOOLS_BY_NAME["run_calculator"].output_schema, "result") == []
    assert structured["score"] == 5
    assert structured["interpretation"]["band"] == "severe"
    assert structured["components"][1]["rule"] == "urea 9.28 mmol/L > 7: +1"
    assert result["content"][0]["text"].startswith("CURB-65")
    assert "RESEARCH USE ONLY" in result["content"][0]["text"]
    assert json.loads(result["content"][1]["text"]) == structured


def test_list_calculators_filters_and_matches_its_schema() -> None:
    server = MedagentMcpServer()
    everything = _call(server, "list_calculators", {})["structuredContent"]
    assert validate(everything, TOOLS_BY_NAME["list_calculators"].output_schema, "result") == []
    assert everything["count"] == 13
    cardiology = _call(server, "list_calculators", {"category": "cardiology"})["structuredContent"]
    assert [c["id"] for c in cardiology["calculators"]] == ["cha2ds2_vasc", "has_bled", "heart"]
    one = _call(server, "list_calculators", {"calculator_id": "news2"})["structuredContent"]
    assert [c["id"] for c in one["calculators"]] == ["news2"]


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            {"calculator_id": "curb_65", "inputs": {**CURB65, "age": 17}},
            "inputs.age must be between",
        ),
        ({"calculator_id": "curb_65", "inputs": {"age": 72}}, "inputs.confusion is required"),
        ({"calculator_id": "curb_65", "inputs": {**CURB65, "urea": 9.3}}, "needs an explicit unit"),
        (
            {"calculator_id": "astrology", "inputs": {}},
            "Invalid arguments: arguments.calculator_id",
        ),
        ({"calculator_id": "curb_65"}, "Invalid arguments: arguments.inputs is required"),
        ({"calculator_id": "curb_65", "inputs": []}, "Invalid arguments: arguments.inputs must be"),
    ],
)
def test_bad_inputs_are_tool_errors_with_the_disclaimer(
    arguments: dict[str, Any], message: str
) -> None:
    result = _call(MedagentMcpServer(), "run_calculator", arguments)
    assert result["isError"] is True
    text = result["content"][0]["text"]
    assert message in text
    assert MANDATORY_DISCLAIMER in text
    assert "structuredContent" not in result


def test_audit_log_records_hashes_not_values(tmp_path: Path) -> None:
    audit = tmp_path / "mcp-audit.jsonl"
    server = MedagentMcpServer(audit_log_path=audit)
    _call(server, "run_calculator", {"calculator_id": "curb_65", "inputs": CURB65})
    row = json.loads(audit.read_text(encoding="utf-8").splitlines()[-1])
    assert row["tool"] == "run_calculator" and row["is_error"] is False
    assert "mg/dL" not in audit.read_text(encoding="utf-8")
