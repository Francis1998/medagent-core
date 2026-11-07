"""Drive the medagent MCP server over real stdio, the way an MCP host does.

Starts ``python -m medagent.mcp`` as a subprocess and exercises both protocol
eras: a modern (2026-07-28) stateless client that probes ``server/discover``,
lists tools, normalises a FHIR bundle and screens it, then a legacy client that
performs the ``initialize`` handshake. No API keys or network access needed.
RESEARCH USE ONLY.

Usage:
    python scripts/mcp_stdio_demo.py
    python scripts/mcp_stdio_demo.py --bundle path/to/bundle.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

MODERN = "2026-07-28"
META: dict[str, Any] = {
    "io.modelcontextprotocol/protocolVersion": MODERN,
    "io.modelcontextprotocol/clientCapabilities": {},
    "io.modelcontextprotocol/clientInfo": {"name": "mcp_stdio_demo", "version": "1.0"},
}
DEFAULT_BUNDLE = (
    Path(__file__).resolve().parent.parent / "data" / "sample_fhir_bundle_polypharmacy.json"
)


class StdioClient:
    """Minimal newline-delimited JSON-RPC client for one server subprocess."""

    def __init__(self) -> None:
        self._process = subprocess.Popen(
            [sys.executable, "-m", "medagent.mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self._next_id = 0

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a request and return its response (the server answers in order)."""
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params})
        assert self._process.stdout is not None
        response: dict[str, Any] = json.loads(self._process.stdout.readline())
        assert response.get("id") == self._next_id, response
        return response

    def notify(self, method: str) -> None:
        """Send a notification (no response expected)."""
        self._send({"jsonrpc": "2.0", "method": method})

    def close(self) -> int:
        """Close stdin (the stdio shutdown signal) and return the exit code."""
        assert self._process.stdin is not None
        self._process.stdin.close()
        return self._process.wait(timeout=10)

    def _send(self, message: dict[str, Any]) -> None:
        assert self._process.stdin is not None
        self._process.stdin.write(json.dumps(message) + "\n")
        self._process.stdin.flush()


def _short(medication: str) -> str:
    return medication.removesuffix(" tablet")


def _identifiers(bundle: dict[str, Any]) -> list[str]:
    """Direct identifiers present in the bundle's Patient resource."""
    values: list[str] = []
    for entry in bundle.get("entry", []):
        patient = entry.get("resource", {})
        if patient.get("resourceType") != "Patient":
            continue
        values += [i["value"] for i in patient.get("identifier", []) if "value" in i]
        values += [part for name in patient.get("name", []) for part in name.get("given", [])]
        values += [name["family"] for name in patient.get("name", []) if "family" in name]
        values += [patient["birthDate"]] if "birthDate" in patient else []
    return values


def modern_session(bundle_path: Path) -> str:
    """Stateless 2026-07-28 client: discover, list, parse, screen, version error."""
    client = StdioClient()
    print(f"→ server/discover   (_meta protocolVersion {MODERN})")
    discover = client.request("server/discover", {"_meta": META})["result"]
    info = discover["_meta"]["io.modelcontextprotocol/serverInfo"]
    print(f"← {info['name']} {info['version']} · supportedVersions {discover['supportedVersions']}")

    print("→ tools/list")
    listed = client.request("tools/list", {"_meta": META})["result"]
    print(f"← ttlMs={listed['ttlMs']} cacheScope={listed['cacheScope']} · tools:")
    print("   " + ", ".join(tool["name"] for tool in listed["tools"]))

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    print(f"→ tools/call parse_fhir_bundle   ({bundle_path.name})")
    parsed = client.request(
        "tools/call", {"name": "parse_fhir_bundle", "arguments": {"bundle": bundle}, "_meta": META}
    )["result"]
    context = parsed["structuredContent"]
    echoed = [value for value in _identifiers(bundle) if value in json.dumps(parsed)]
    print(
        f"← patient {context['patient_id_hash'][:12]}… (hashed) · age {context['age']} · "
        f"{len(context['medications'])} active meds · egfr "
        f"{context['screening_input']['patient'].get('egfr')} · identifiers echoed: {len(echoed)}"
    )

    print("→ tools/call screen_medications   (arguments = screening_input)")
    screened = client.request(
        "tools/call",
        {"name": "screen_medications", "arguments": context["screening_input"], "_meta": META},
    )["result"]["structuredContent"]
    print(
        f"← {screened['finding_count']} findings · highest {screened['highest_severity']} · "
        f"escalation_recommended={screened['escalation_recommended']}"
    )
    for finding in screened["findings"]:
        involved = " + ".join(_short(name) for name in finding["medications"])
        print(f"   {finding['severity']:<8} {finding['check_id']:<18} {involved}")
    skipped = ", ".join(check["check_id"] for check in screened["checks_skipped"])
    print(f"   not run (missing context): {skipped}")

    print("→ tools/list   (_meta protocolVersion 1900-01-01)")
    error = client.request(
        "tools/list",
        {"_meta": {**META, "io.modelcontextprotocol/protocolVersion": "1900-01-01"}},
    )["error"]
    print(f"← error {error['code']} {error['message']} · supported {error['data']['supported']}")
    print(f"   stdin closed → server exit code {client.close()}")
    return str(screened["disclaimer"])


def legacy_session() -> None:
    """Legacy client: initialize handshake, then a tool call with legacy result shape."""
    client = StdioClient()
    print("→ initialize   protocolVersion 2025-06-18   (legacy client)")
    initialized = client.request(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "legacy-demo", "version": "1.0"},
        },
    )["result"]
    client.notify("notifications/initialized")
    print(
        f"← protocolVersion {initialized['protocolVersion']} · "
        f"serverInfo {initialized['serverInfo']['name']}"
    )
    print("→ tools/call check_drug_interactions   [warfarin 5 mg, fluconazole 150 mg]")
    result = client.request(
        "tools/call",
        {
            "name": "check_drug_interactions",
            "arguments": {"medications": ["warfarin 5 mg", "fluconazole 150 mg"]},
        },
    )["result"]
    findings = "; ".join(
        f"{finding['severity']} {finding['check_id']}"
        for finding in result["structuredContent"]["findings"]
    )
    shape = "no resultType (legacy shape)" if "resultType" not in result else result["resultType"]
    print(f"← isError={result['isError']} · {shape} · {findings}")
    print(f"   stdin closed → server exit code {client.close()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    args = parser.parse_args()
    disclaimer = modern_session(args.bundle)
    legacy_session()
    print(f"Every result carries: {disclaimer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
