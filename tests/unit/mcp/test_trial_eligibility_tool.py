"""MCP tests for ``screen_trial_eligibility`` across both protocol eras."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from medagent.mcp.schema import validate
from medagent.mcp.server import MedagentMcpServer
from medagent.mcp.tools import TOOLS_BY_NAME
from medagent.safety.disclaimer import MANDATORY_DISCLAIMER
from medagent.safety.pii_hasher import hash_pii

EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "trials"
TOOL = "screen_trial_eligibility"
MODERN_META: dict[str, Any] = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientCapabilities": {},
    "io.modelcontextprotocol/clientInfo": {"name": "pytest", "version": "1.0"},
}


def _arguments(**extra: Any) -> dict[str, Any]:
    return {
        "bundle": json.loads((EXAMPLES / "patient-bundle.json").read_text(encoding="utf-8")),
        "trials": json.loads((EXAMPLES / "example-trials.json").read_text(encoding="utf-8")),
        "as_of": "2026-11-12",
        **extra,
    }


def _call(server: MedagentMcpServer, arguments: Any, *, modern: bool = True) -> dict[str, Any]:
    params: dict[str, Any] = {"name": TOOL, "arguments": arguments}
    if modern:
        params["_meta"] = MODERN_META
    response = server.handle_message(
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": params}
    )
    assert response is not None and "result" in response, response
    return dict(response["result"])


def _legacy_server() -> MedagentMcpServer:
    server = MedagentMcpServer()
    server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "x"},
            },
        }
    )
    return server


def test_the_tool_is_listed_in_both_eras_with_read_only_schemas() -> None:
    modern = MedagentMcpServer().handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"_meta": MODERN_META}}
    )
    legacy = _legacy_server().handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

    assert modern is not None and legacy is not None
    for listed in (modern["result"]["tools"], legacy["result"]["tools"]):
        tool = next(item for item in listed if item["name"] == TOOL)
        assert tool["inputSchema"]["required"] == ["bundle", "trials"]
        assert tool["inputSchema"]["additionalProperties"] is False
        assert tool["outputSchema"]["properties"]["disclaimer"]["const"] == MANDATORY_DISCLAIMER
        assert tool["annotations"] == {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
        assert "never an eligibility determination" in tool["description"]


def test_modern_and_legacy_calls_return_the_same_structured_content() -> None:
    modern = _call(MedagentMcpServer(), _arguments())
    legacy = _call(_legacy_server(), _arguments(), modern=False)

    assert modern["isError"] is False and legacy["isError"] is False
    assert modern["resultType"] == "complete"
    assert "resultType" not in legacy
    assert modern["structuredContent"] == legacy["structuredContent"]
    structured = modern["structuredContent"]
    assert validate(structured, TOOLS_BY_NAME[TOOL].output_schema, "result") == []
    assert [trial["status"] for trial in structured["trials"]] == [
        "potentially_eligible",
        "needs_review",
        "needs_review",
        "likely_ineligible",
    ]
    text, serialised = modern["content"]
    assert text["text"].startswith("medagent screen_trial_eligibility: 4 trial(s) pre-screened")
    assert text["text"].endswith(MANDATORY_DISCLAIMER)
    assert json.loads(serialised["text"]) == structured


def test_invalid_trials_and_fhir_are_tool_errors_with_the_disclaimer() -> None:
    server = MedagentMcpServer()
    unsupported_unit = _arguments()
    unsupported_unit["trials"][0]["inclusion"][1]["unit"] = "mg/furlong"
    two_patients = _arguments()
    two_patients["bundle"]["entry"].append({"resource": {"resourceType": "Patient", "id": "other"}})

    results = [
        _call(server, {"bundle": _arguments()["bundle"]}),
        _call(server, unsupported_unit),
        _call(server, two_patients),
    ]

    messages = [result["content"][0]["text"] for result in results]
    assert all(result["isError"] is True for result in results)
    assert all(message.endswith(MANDATORY_DISCLAIMER) for message in messages)
    assert messages[0].startswith("Invalid arguments: arguments.trials is required")
    assert messages[1].startswith("trials[0].inclusion[1].unit is not a supported unit")
    assert messages[2].startswith("FHIR data rejected: Bundle contains 2 Patient resources")


def test_calls_are_audited_with_hashes_only(tmp_path: Path) -> None:
    audit_path = tmp_path / "mcp-audit.jsonl"
    server = MedagentMcpServer(audit_log_path=audit_path)

    result = _call(server, _arguments(patient_ref="caller-ref-CANARY"))

    [record] = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    structured = result["structuredContent"]
    assert record["tool"] == TOOL
    assert record["is_error"] is False
    assert record["inputs_hash"] == structured["inputs_hash"]
    assert record["patient_id_hash"] == structured["patient_id_hash"]
    assert record["patient_ref_hash"] == hash_pii("caller-ref-CANARY")
    written = audit_path.read_text(encoding="utf-8")
    for value in (
        "caller-ref-CANARY",
        "MRN-TRIAL-DEMO-0007",
        "Rowan",
        "Apixaban",
        "EXAMPLE-ONC-001",
    ):
        assert value not in written
