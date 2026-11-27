#!/usr/bin/env bash
# Replay the rubric evaluation demo and print a transcript.
#
# Each command below is printed with a "$ " prefix and then executed verbatim, so
# the output is exactly what medagent returned. Needs jq and `python` resolving to
# the environment medagent is installed in; no LLM keys or network access. Every
# case and answer is synthetic and PHI-free. RESEARCH USE ONLY.
#
# Usage (from the repository root):
#   bash scripts/rubric_eval_demo.sh > docs/guides/rubric_eval_demo_transcript.txt

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
# 12 synthetic HealthBench-format cases on medagent's safety behaviours
D=examples/rubric_eval; R="--responses careful=$D/responses_careful.jsonl --responses risky=$D/responses_risky.jsonl"
python -m medagent.evals validate --dataset $D/safety_rubrics.jsonl $R
# grade two recorded answer sets and medagent's own offline pipeline (no keys, no network)
python -m medagent.evals run --dataset $D/safety_rubrics.jsonl $R --generate-offline --output results/rubric_demo
# per-axis breakdown from the Markdown report
sed -n '/^## By axis/,/^## By theme/p' results/rubric_demo.md | grep '^|'
# why medagent-offline lost points on the chest-pain red flag: verdict, points, reason
jq -r '.configurations[2].examples[0].grades[] | "\(.verdict)  \(.points)  \(.reason)"' results/rubric_demo.json
# CI gate: exit 1 when a configuration scores below --fail-under
python -m medagent.evals run --dataset $D/safety_rubrics.jsonl $R --fail-under 0.5 --output results/rubric_gate 2>&1 | grep -E "^(careful|risky) |below"; echo "exit ${PIPESTATUS[0]}"
# invalid input: file, line and field are named, the clinical text never is (exit 2)
echo '{"prompt_id": "x", "prompt": "crushing chest pain"}' > results/bad.jsonl; python -m medagent.evals validate --dataset results/bad.jsonl; echo "exit $?"
COMMANDS
