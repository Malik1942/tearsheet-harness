#!/usr/bin/env bash
# Gate run for Bricks: one Muse Spark extraction per photo (see docs/GATE.md).
#
# Dry-run by default: prints each request and its cost estimate, sends nothing, needs no key.
#
#   scripts/gate.sh                        dry-run every photo in fixtures/images/ (names starting with _ are skipped)
#   scripts/gate.sh a.jpg b.jpg c.jpg      dry-run these photos (paths relative to meta-eval/, or absolute)
#   scripts/gate.sh --send [photos]        real calls, one per photo; each run is budget-checked by the harness
#   scripts/gate.sh --effort medium ...    reasoning effort: minimal | low | medium | high | xhigh | max
#
# Knobs (environment): EFFORT=medium  MAX_OUT=12000  MAX_SIDE=2048
#                      PROMPT_FILE=fixtures/prompts/extract_brick.md  SCHEMA_FILE=fixtures/schemas/brick.json
# An unparseable response or a local failure does not stop the other photos (exit 1 at the end);
# an HTTP 4xx from the API stops everything at once (exit 4).
set -euo pipefail
cd "$(dirname "$0")/.."

SEND=0
PHOTOS=()
EFFORT_FLAG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --send) SEND=1 ;;
    --effort) [ $# -ge 2 ] || { echo "gate: --effort needs a value" >&2; exit 2; }; EFFORT_FLAG="$2"; shift ;;
    --effort=*) EFFORT_FLAG="${1#--effort=}" ;;
    -h|--help) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "gate: unknown option $1 (try --help)" >&2; exit 2 ;;
    *) PHOTOS+=("$1") ;;
  esac
  shift
done

if [ "${#PHOTOS[@]}" -eq 0 ]; then
  shopt -s nullglob nocaseglob
  for f in fixtures/images/*.jpg fixtures/images/*.jpeg fixtures/images/*.png; do
    case "$(basename "$f")" in _*) ;; *) PHOTOS+=("$f") ;; esac
  done
  shopt -u nullglob nocaseglob
fi
if [ "${#PHOTOS[@]}" -eq 0 ]; then
  if [ "$SEND" -eq 1 ]; then
    echo "gate: no photos in fixtures/images/ (jpg, jpeg or png; names starting with _ are skipped); nothing sent" >&2
    exit 1
  fi
  echo "gate: no real photos in fixtures/images/ yet; dry-running the placeholder"
  PHOTOS=(fixtures/images/_placeholder.jpg)
fi

dupes="$(for f in "${PHOTOS[@]}"; do basename "${f%.*}"; done | sort | uniq -d)"
if [ -n "$dupes" ]; then
  echo "gate: two photos share a name stem ($(echo "$dupes" | tr '\n' ' ')); their results would overwrite each other in out/<stem>/. Rename one." >&2
  exit 1
fi

EFFORT="${EFFORT_FLAG:-${EFFORT:-medium}}"
case "$EFFORT" in minimal|low|medium|high|xhigh|max) ;; *) echo "gate: invalid effort '$EFFORT'" >&2; exit 2 ;; esac
MAX_OUT="${MAX_OUT:-12000}"
MAX_SIDE="${MAX_SIDE:-2048}"
PROMPT_FILE="${PROMPT_FILE:-fixtures/prompts/extract_brick.md}"
SCHEMA_FILE="${SCHEMA_FILE:-fixtures/schemas/brick.json}"
PY=.venv/bin/python
[ -x "$PY" ] || { echo "gate: $PY not found; see README setup" >&2; exit 1; }
[ -f "$PROMPT_FILE" ] || { echo "gate: prompt file $PROMPT_FILE not found" >&2; exit 1; }
[ -n "$(tr -d '[:space:]' < "$PROMPT_FILE")" ] || { echo "gate: prompt file $PROMPT_FILE is empty" >&2; exit 1; }
[ -f "$SCHEMA_FILE" ] || { echo "gate: schema file $SCHEMA_FILE not found" >&2; exit 1; }

MODE="dry run"
DRY=(--dry-run)
if [ "$SEND" -eq 1 ]; then MODE="SENDING"; DRY=(); fi

echo "gate: ${#PHOTOS[@]} photo(s); effort=$EFFORT max_output_tokens=$MAX_OUT max_side=$MAX_SIDE; prompt=$PROMPT_FILE; schema=$SCHEMA_FILE; $MODE"
FAILED=()
for photo in "${PHOTOS[@]}"; do
  echo
  echo "=== $photo ==="
  rc=0
  "$PY" -m meta_eval.spark_vision "$photo" --task describe-json --schema "$SCHEMA_FILE" \
    --prompt="$(cat "$PROMPT_FILE")" --effort "$EFFORT" --max-output-tokens "$MAX_OUT" --max-side "$MAX_SIDE" \
    ${DRY[@]+"${DRY[@]}"} \
    || { rc=$?; echo "gate: $photo FAILED (exit $rc); if a call was made, its status, usage and raw text are in out/$(basename "${photo%.*}")/spark_vision.json" >&2; FAILED+=("$photo"); }
  if [ "$rc" -eq 4 ]; then
    echo "gate: the API returned a 4xx. Stopping everything; nothing more is sent. Report before any resend." >&2
    if [ "$SEND" -eq 1 ]; then echo; "$PY" -m meta_eval.costs summary; fi
    exit 4
  fi
  [ "$rc" -eq 0 ] || echo "gate: continuing with the next photo" >&2
done

if [ "$SEND" -eq 1 ]; then
  echo
  "$PY" -m meta_eval.costs summary
fi
if [ "${#FAILED[@]}" -gt 0 ]; then
  echo
  echo "gate: failed photo(s): ${FAILED[*]}" >&2
  echo "gate: re-send ONLY these, by path (scripts/gate.sh --send <photo>). A bare --send would re-sample the photos that already succeeded and overwrite their results." >&2
  exit 1
fi
