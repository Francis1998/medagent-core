#!/usr/bin/env bash
# Replay the clinical-trial eligibility pre-screening demo and print a transcript.
#
# Each command below is printed with a "$ " prefix and then executed verbatim, so
# the output is exactly what medagent returned. Needs curl, jq and sqlite3, the
# API started from the repository root (so the default DATABASE_URL writes
# data/audit.db), `python` resolving to the environment medagent is installed in
# (for the MCP step), and no LLM keys or network access. Set MEDAGENT_URL when the
# API is not on localhost:8000. Every trial and the patient are synthetic.
# RESEARCH USE ONLY.
#
# Usage (from the repository root):
#   PII_HASH_SALT=demo-only-salt medagent --port 8000 &
#   PII_HASH_SALT=demo-only-salt bash scripts/trial_eligibility_demo.sh \
#     > docs/guides/trial_eligibility_demo_transcript.txt

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
# 1 synthetic FHIR R4 patient x 4 fictional trials (EXAMPLE-* ids), evaluated as of 2026-11-12
URL=${MEDAGENT_URL:-localhost:8000}/trials/eligibility; H='Content-Type: application/json'; REQ='{bundle: .[0], trials: .[1], as_of: "2026-11-12"}'
jq -s "$REQ" examples/trials/patient-bundle.json examples/trials/example-trials.json | curl -s -X POST $URL -H "$H" -d @- | jq -r '.trials[] | "#\(.rank) \(.trial_id)  \(.rank_reason)"'
# criterion-level trace for EXAMPLE-ONC-001
jq -s "$REQ" examples/trials/patient-bundle.json examples/trials/example-trials.json | curl -s -X POST $URL -H "$H" -d @- | jq -r '.trials[] | select(.trial_id == "EXAMPLE-ONC-001") | .criteria[] | "\(.status)  \(.criterion_id): \(.rationale)"'
# breastfeeding status is never guessed; once the caller asserts it, ONC-001 has no open criteria
jq -s "$REQ + {patient_context: {breastfeeding: false}}" examples/trials/patient-bundle.json examples/trials/example-trials.json | curl -s -X POST $URL -H "$H" -d @- | jq -c '.trials[] | {rank, trial_id, status, blocking_criteria}'
# an invalid trial definition is a 422 that names the path, never the value (and never a 500)
jq -s "$REQ | .trials[0].inclusion[1].unit = \"mg/furlong\"" examples/trials/patient-bundle.json examples/trials/example-trials.json | curl -s -w '  HTTP %{http_code}\n' -X POST $URL -H "$H" -d @-
# the same evaluator over MCP: one stateless 2026-07-28 tools/call to python -m medagent.mcp
jq -nc --slurpfile b examples/trials/patient-bundle.json --slurpfile t examples/trials/example-trials.json '{jsonrpc: "2.0", id: 1, method: "tools/call", params: {name: "screen_trial_eligibility", arguments: {bundle: $b[0], trials: $t[0], as_of: "2026-11-12"}, _meta: {"io.modelcontextprotocol/protocolVersion": "2026-07-28", "io.modelcontextprotocol/clientCapabilities": {}}}}' | python -m medagent.mcp | jq -r '.result.content[0].text'
# audit trail of the HTTP calls: hashes, ids, statuses and counts only
sqlite3 data/audit.db "select event, trial_id, status, trial_rank, blocking_criteria from trial_screening_audit order by id desc limit 4"
grep -a -c -E 'Rowan|MRN-TRIAL-DEMO|1961-05-14|Apixaban|Non-small' data/audit.db
COMMANDS

# The last grep exits 1 when it finds nothing, which is the expected result.
exit 0
