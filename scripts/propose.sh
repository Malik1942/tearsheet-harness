#!/usr/bin/env bash
# Proposal regression (PRD 10.2): one Muse Spark TEXT call per intent, against the sample library (see docs/PROPOSE.md).
#
# Dry-run by default: prints each request and its cost estimate, sends nothing, needs no key.
#
#   scripts/propose.sh                      dry-run every intent in fixtures/propose_notes.md (the "## Intent:" headings)
#   scripts/propose.sh "a menu for a bakery" dry-run this intent
#   scripts/propose.sh --send [intents]     real calls, one per intent; budget-checked by the harness
#   scripts/propose.sh --effort low ...     reasoning effort (the product sends low)
#
# Knobs (environment): EFFORT=low  MAX_OUT=4000  LIBRARY=../bricks/src/fixtures/samples
#                      PROMPT_FILE=fixtures/prompts/propose.md  SCHEMA_FILE=fixtures/schemas/propose.json
#                      NOTES=fixtures/propose_notes.md (the sealed set to read intents from and score against)
#                      OUT_DIR=out/propose (a second set should get its own, e.g. OUT_DIR=out/propose_v2)
# Only the heading line of each intent is read before a call; the rest of the sealed notes is read after it, to score.
# An unparseable response does not stop the other intents (exit 1 at the end); an HTTP 4xx stops everything (exit 4).
set -euo pipefail
cd "$(dirname "$0")/.."

SEND=0
INTENTS=()
EFFORT_FLAG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --send) SEND=1 ;;
    --effort) [ $# -ge 2 ] || { echo "propose: --effort needs a value" >&2; exit 2; }; EFFORT_FLAG="$2"; shift ;;
    --effort=*) EFFORT_FLAG="${1#--effort=}" ;;
    -h|--help) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "propose: unknown option $1 (try --help)" >&2; exit 2 ;;
    *) INTENTS+=("$1") ;;
  esac
  shift
done

NOTES="${NOTES:-fixtures/propose_notes.md}"
OUT_DIR="${OUT_DIR:-out/propose}"
if [ "${#INTENTS[@]}" -eq 0 ]; then
  if [ ! -f "$NOTES" ]; then
    echo "propose: $NOTES not found. Seal it first (docs/PROPOSE.md), or pass intents on the command line for a dry run." >&2
    [ "$SEND" -eq 1 ] && exit 1
    INTENTS=("a one-page menu for a small bakery")
  else
    while IFS= read -r line; do INTENTS+=("$line"); done < <(sed -n 's/^## Intent:[[:space:]]*//p' "$NOTES" | sed 's/^"//; s/"$//')
    if [ "${#INTENTS[@]}" -eq 0 ]; then echo "propose: no '## Intent:' heading in $NOTES" >&2; exit 1; fi
  fi
fi
if [ "$SEND" -eq 1 ] && [ ! -f "$NOTES" ]; then echo "propose: sealed notes are required before a real call" >&2; exit 1; fi

EFFORT="${EFFORT_FLAG:-${EFFORT:-low}}"
MAX_OUT="${MAX_OUT:-4000}"
LIBRARY="${LIBRARY:-../bricks/src/fixtures/samples}"
PROMPT_FILE="${PROMPT_FILE:-fixtures/prompts/propose.md}"
SCHEMA_FILE="${SCHEMA_FILE:-fixtures/schemas/propose.json}"
PY=.venv/bin/python
[ -x "$PY" ] || { echo "propose: $PY not found; see README setup" >&2; exit 1; }
[ -f "$PROMPT_FILE" ] || { echo "propose: prompt file $PROMPT_FILE not found" >&2; exit 1; }
[ -f "$SCHEMA_FILE" ] || { echo "propose: schema file $SCHEMA_FILE not found" >&2; exit 1; }
[ -d "$LIBRARY" ] || { echo "propose: library dir $LIBRARY not found" >&2; exit 1; }

MODE="dry run"; DRY=(--dry-run)
if [ "$SEND" -eq 1 ]; then MODE="SENDING"; DRY=(); fi
echo "propose: ${#INTENTS[@]} intent(s); effort=$EFFORT max_output_tokens=$MAX_OUT; library=$LIBRARY; prompt=$PROMPT_FILE; schema=$SCHEMA_FILE; notes=$NOTES; out=$OUT_DIR; $MODE"
FAILED=()
for intent in "${INTENTS[@]}"; do
  echo
  echo "=== $intent ==="
  rc=0
  "$PY" -m meta_eval.propose --intent "$intent" --library "$LIBRARY" --prompt "$PROMPT_FILE" --schema "$SCHEMA_FILE" \
    --effort "$EFFORT" --max-output-tokens "$MAX_OUT" --notes "$NOTES" --out-dir "$OUT_DIR" ${DRY[@]+"${DRY[@]}"} \
    || { rc=$?; echo "propose: '$intent' FAILED (exit $rc)" >&2; FAILED+=("$intent"); }
  if [ "$rc" -eq 4 ]; then echo "propose: HTTP 4xx; stopping before the next intent" >&2; exit 4; fi
done
echo
if [ "${#FAILED[@]}" -gt 0 ]; then echo "propose: ${#FAILED[@]} intent(s) failed"; exit 1; fi
[ "$SEND" -eq 1 ] && "$PY" -m meta_eval.costs summary
echo "propose: done ($MODE)"
