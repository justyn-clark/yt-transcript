#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${YT_TRANSCRIPT_REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
QUEUE_DIR="${YT_TRANSCRIPT_QUEUE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/yt-transcript/queue}"
QUEUE_FILE="${YT_TRANSCRIPT_QUEUE_FILE:-$QUEUE_DIR/inbox.txt}"
PROCESSED_FILE="${YT_TRANSCRIPT_PROCESSED_FILE:-$QUEUE_DIR/processed.tsv}"
FAILED_FILE="${YT_TRANSCRIPT_FAILED_FILE:-$QUEUE_DIR/failed.tsv}"
LOG_DIR="${YT_TRANSCRIPT_LOG_DIR:-$QUEUE_DIR/logs}"
NOTES_DIR="${YT_TRANSCRIPT_NOTES_DIR:-$HOME/Documents/yt-transcript-notes}"
NOTES_SUBDIR="${YT_TRANSCRIPT_NOTES_SUBDIR:-Transcripts/YouTube}"
DATABASE_ENABLED="${YT_TRANSCRIPT_DATABASE_ENABLED:-false}"
LOCK_DIR="$QUEUE_DIR/.process.lock"
PYTHON_BIN="${YT_TRANSCRIPT_PYTHON:-python3}"
CLI_BIN="${YT_TRANSCRIPT_CLI:-}"

if [[ -z "$CLI_BIN" ]]; then
  if [[ -x "$REPO_DIR/.venv/bin/yt-transcript" ]]; then
    CLI_BIN="$REPO_DIR/.venv/bin/yt-transcript"
    PYTHON_BIN="$REPO_DIR/.venv/bin/python"
  elif command -v yt-transcript >/dev/null 2>&1; then
    CLI_BIN="$(command -v yt-transcript)"
  else
    echo "yt-transcript CLI not found. Install this package or set YT_TRANSCRIPT_CLI=/path/to/yt-transcript." >&2
    exit 2
  fi
fi

mkdir -p "$QUEUE_DIR" "$LOG_DIR" "$NOTES_DIR"
touch "$QUEUE_FILE" "$PROCESSED_FILE" "$FAILED_FILE"

db_enabled=false
case "$DATABASE_ENABLED" in
  1|[Tt][Rr][Uu][Ee]|[Yy][Ee][Ss]|[Oo][Nn]) db_enabled=true ;;
esac

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Another yt-transcript queue run is active; exiting."
  exit 0
fi
cleanup_lock() { rmdir "$LOCK_DIR" 2>/dev/null || true; }
trap cleanup_lock EXIT

run_id="$(date -u +%Y%m%dT%H%M%SZ)"
run_log="$LOG_DIR/$run_id.log"
tmp_pending="$(mktemp)"
tmp_unique="$(mktemp)"
cleanup() { rm -f "$tmp_pending" "$tmp_unique"; cleanup_lock; }
trap cleanup EXIT

# Keep non-empty, non-comment lines. Preserve order while de-duping within this run.
grep -vE '^[[:space:]]*($|#)' "$QUEUE_FILE" > "$tmp_pending" || true
awk '!seen[$0]++' "$tmp_pending" > "$tmp_unique"

if [[ ! -s "$tmp_unique" ]]; then
  echo "[$run_id] No queued YouTube URLs." | tee -a "$run_log"
  exit 0
fi

: > "$QUEUE_FILE"

echo "[$run_id] Processing $(wc -l < "$tmp_unique" | tr -d ' ') queued URL(s)." | tee -a "$run_log"

while IFS= read -r url; do
  [[ -n "$url" ]] || continue
  echo "[$run_id] START $url" | tee -a "$run_log"
  url_hash="$(printf '%s' "$url" | shasum -a 256 | cut -c1-12)"
  out_file="$LOG_DIR/$run_id.$url_hash.json"
  err_file="$LOG_DIR/$run_id.$url_hash.err"
  parse_err_file="$LOG_DIR/$run_id.$url_hash.parse.err"
  cli_args=(youtube "$url" --json)
  if [[ "$db_enabled" != true ]]; then
    cli_args+=(--no-db)
  fi

  if YT_TRANSCRIPT_DATABASE_ENABLED="$DATABASE_ENABLED" \
     YT_TRANSCRIPT_NOTES_DIR="$NOTES_DIR" \
     YT_TRANSCRIPT_NOTES_SUBDIR="$NOTES_SUBDIR" \
     "$CLI_BIN" "${cli_args[@]}" >"$out_file" 2>"$err_file"; then
    if parsed="$($PYTHON_BIN - "$out_file" "$db_enabled" 2>"$parse_err_file" <<'PY'
import json, sys
p = sys.argv[1]
db_enabled = sys.argv[2] == "true"
data = json.load(open(p))
errors = []
if data.get("status") != "done":
    errors.append(f"status={data.get('status')}")
if db_enabled and data.get("db_status") != "ok":
    errors.append(f"db_status={data.get('db_status')}")
if data.get("notes_status") != "ok":
    errors.append(f"notes_status={data.get('notes_status')}")
if errors:
    raise SystemExit("; ".join(errors))
fields = [
    data.get("source_id", ""),
    data.get("retrieval_method", ""),
    str(data.get("segment_count", "")),
    data.get("notes_path", ""),
    data.get("title", ""),
]
print("\t".join(str(x).replace("\t", " ") for x in fields))
PY
    )"; then
      printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$url" "$parsed" >> "$PROCESSED_FILE"
      echo "[$run_id] OK $url -> $parsed" | tee -a "$run_log"
    else
      msg="$(tr '\n' ' ' < "$parse_err_file" | cut -c1-500)"
      printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$url" "$msg" >> "$FAILED_FILE"
      echo "[$run_id] FAILED $url :: $msg" | tee -a "$run_log"
    fi
  else
    msg="$(tr '\n' ' ' < "$err_file" | cut -c1-500)"
    if [[ -z "$msg" ]]; then msg="$(tr '\n' ' ' < "$out_file" | cut -c1-500)"; fi
    printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$url" "$msg" >> "$FAILED_FILE"
    echo "[$run_id] FAILED $url :: $msg" | tee -a "$run_log"
  fi
done < "$tmp_unique"

echo "[$run_id] Done. Processed log: $PROCESSED_FILE; failed log: $FAILED_FILE" | tee -a "$run_log"
