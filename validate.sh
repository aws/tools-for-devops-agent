#!/usr/bin/env bash
# Re-runs the structural validation on the local mirror of the PR.
set -u
cd "$(dirname "$0")"
SKILL="skills/datalake-access-analyzer"
fail=0

echo "=== 1. File layout ==="
for f in SKILL.md README.md references/permission-chain.md evals/evals.json; do
  if [ -f "$SKILL/$f" ]; then
    echo "  OK   $SKILL/$f"
  else
    echo "  MISS $SKILL/$f"; fail=1
  fi
done

echo "=== 2. evals.json valid + scenario count ==="
if python3 -c "import json,sys; d=json.load(open('$SKILL/evals/evals.json')); n=len(d['scenarios']); print('  OK   valid JSON, scenarios =', n); sys.exit(0 if n==5 else 1)"; then
  :
else
  echo "  FAIL evals.json invalid or scenario count != 5"; fail=1
fi

echo "=== 3. SKILL.md line count (<= 500) ==="
lines=$(wc -l < "$SKILL/SKILL.md" | tr -d ' ')
if [ "$lines" -le 500 ]; then echo "  OK   $lines lines"; else echo "  FAIL $lines lines (> 500)"; fail=1; fi

echo "=== 4. No internal references in shipped files ==="
if grep -rniE 'glue ?#|pattern [0-9]|amzn-|a2z\.com|w\.amazon\.com|harmony|internal-only' "$SKILL" ; then
  echo "  FAIL internal reference found above"; fail=1
else
  echo "  OK   no internal references"
fi

echo
if [ "$fail" -eq 0 ]; then echo "ALL CHECKS PASSED"; else echo "SOME CHECKS FAILED"; fi
exit $fail
