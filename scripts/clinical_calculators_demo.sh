#!/usr/bin/env bash
# Replay the clinical calculators demo and print a transcript.
#
# Each command below is printed with a "$ " prefix and then executed verbatim, so
# the output is exactly what medagent returned. Needs curl and jq, the API
# running, `python` resolving to the environment medagent is installed in (for
# the MCP step), and no LLM keys or network access. Set MEDAGENT_URL when the API
# is not on localhost:8000. Every patient value is synthetic. RESEARCH USE ONLY.
#
# Usage (from the repository root):
#   PII_HASH_SALT=demo-only-salt medagent --port 8000 &
#   bash scripts/clinical_calculators_demo.sh > docs/guides/clinical_calculators_demo_transcript.txt

cd "$(dirname "$0")/.." || exit 1

while IFS= read -r command; do
  [[ -z "$command" ]] && continue
  if [[ "$command" == \#* ]]; then
    printf '%s\n' "$command"
    continue
  fi
  printf '$ %s\n' "$command"
  eval "$command" < /dev/null
done <<'COMMANDS'
# 13 audited calculators, each with typed inputs (units, ranges, choices) and a citation
URL=${MEDAGENT_URL:-localhost:8000}/calculators; H='Content-Type: application/json'
curl -s $URL | jq -r '.calculators[] | "\(.id) [\(.category)] " + (if .citation.doi then "doi:" + .citation.doi elif .citation.pmid then "PMID " + .citation.pmid else .citation.url end)'
# CURB-65 from raw values: BUN 26 mg/dL is converted to urea mmol/L; each criterion shows the rule that fired
curl -s -X POST $URL/curb_65 -H "$H" -d '{"inputs": {"confusion": false, "urea": {"value": 26, "unit": "mg/dL"}, "respiratory_rate": 31, "systolic_bp": 118, "diastolic_bp": 72, "age": 72}}' | jq -r '"score \(.score) -> \(.interpretation.label) (\(.interpretation.range))", (.components[] | "  \(.points)  \(.rule)")'
# MELD-Na in SI units: the OPTN formula terms are returned, not just the total
curl -s -X POST $URL/meld_na -H "$H" -d '{"inputs": {"bilirubin": {"value": 42.75, "unit": "µmol/L"}, "inr": 1.8, "creatinine": {"value": 168, "unit": "µmol/L"}, "sodium": 129, "dialysis": false}}' | jq -r '"MELD-Na \(.score): \(.interpretation.description)", (.components[] | "  \(.rule)")'
# race-free CKD-EPI 2021 eGFR: the band uses the unrounded value; labs report the whole number
curl -s -X POST $URL/ckd_epi_2021 -H "$H" -d '{"inputs": {"creatinine": {"value": 1.3, "unit": "mg/dL"}, "age": 67, "sex": "female"}}' | jq -c '{score, egfr_rounded: .details.egfr_rounded, band: .interpretation.label, doi: .citations[0].doi}'
# a missing input is a 422 that names it (never silently "absent"); a creatinine without a unit is rejected
curl -s -w '  HTTP %{http_code}\n' -X POST $URL/ckd_epi_2021 -H "$H" -d '{"inputs": {"creatinine": 1.3, "age": 67}}'
# the same registry over MCP: one stateless 2026-07-28 tools/call of run_calculator
jq -nc '{jsonrpc: "2.0", id: 1, method: "tools/call", params: {name: "run_calculator", arguments: {calculator_id: "news2", inputs: {respiratory_rate: 22, oxygen_saturation: 95, supplemental_oxygen: false, systolic_bp: 105, heart_rate: 112, consciousness: "alert", temperature: {value: 101.3, unit: "°F"}}}, _meta: {"io.modelcontextprotocol/protocolVersion": "2026-07-28", "io.modelcontextprotocol/clientCapabilities": {}}}}' | python -m medagent.mcp 2>/dev/null | jq -r '.result.content[0].text'
COMMANDS
