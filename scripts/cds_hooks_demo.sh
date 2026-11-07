#!/usr/bin/env bash
# Replay the CDS Hooks demo against a running medagent API and print a transcript.
#
# Each command below is printed with a "$ " prefix and then executed verbatim, so
# the output is exactly what the service returned. Needs curl, jq and sqlite3, the
# API on localhost:8000 started from the repository root (so the default
# DATABASE_URL writes data/audit.db), and no LLM keys or network access.
# RESEARCH USE ONLY.
#
# Usage (from the repository root):
#   PII_HASH_SALT=demo-only-salt medagent --port 8000 &
#   bash scripts/cds_hooks_demo.sh > docs/guides/cds_hooks_demo_transcript.txt

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
curl -s localhost:8000/cds-services | jq -c '.services[] | {id, hook, prefetch: (.prefetch | keys)}'
SIGN=localhost:8000/cds-services/medagent-medication-safety; H='Content-Type: application/json'
# order-sign: draft fluconazole + prefetched warfarin, metformin, penicillin allergy, eGFR 28
curl -s -X POST $SIGN -H "$H" -d @examples/cds_hooks/order-sign.json | jq -r '.cards[] | "\(.indicator)  \(.summary)"'
curl -s -X POST $SIGN -H "$H" -d @examples/cds_hooks/order-sign.json | jq -r '.cards[0].detail' | grep -E 'involved|warfarin_azole|Escalation'
# the same call without prefetch: drafts only, and an info card names the gaps
jq 'del(.prefetch)' examples/cds_hooks/order-sign.json | curl -s -X POST $SIGN -H "$H" -d @- | jq -r '.cards[] | "\(.indicator)  \(.summary)"'
# order-select: only findings that involve the selected order (amoxicillin)
curl -s -X POST $SIGN-select -H "$H" -d @examples/cds_hooks/order-select.json | jq -r '.cards[] | "\(.indicator)  \(.summary)"'
jq '.context.draftOrders.entry[0].resource.medicationCodeableConcept = {text: "Acetaminophen 500 mg tablet"}' examples/cds_hooks/order-sign.json | curl -s -X POST $SIGN -H "$H" -d @-; echo
jq '.prefetch.patient.id = "another-patient"' examples/cds_hooks/order-sign.json | curl -s -w '  HTTP %{http_code}\n' -X POST $SIGN -H "$H" -d @-
# feedback: card uuid, outcome and override reason code are audited; the comment is not
CARD=$(curl -s -X POST $SIGN -H "$H" -d @examples/cds_hooks/order-sign.json | jq -r '.cards[0].uuid')
jq --arg c "$CARD" '.feedback[0].card = $c' examples/cds_hooks/feedback.json | curl -s -X POST $SIGN/feedback -H "$H" -d @-; echo
sqlite3 data/audit.db "select event, check_ids, outcome, override_reason_code from cds_hooks_audit where card_uuid = '$CARD'"
grep -a -c -E 'cds-demo-ada|demo-prescriber|Fluconazole|Free-text' data/audit.db
COMMANDS

# The last grep exits 1 when it finds nothing, which is the expected result.
exit 0
