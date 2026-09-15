#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM HUP
STATE="$TMP/state"
CODEX_HOME="$TMP/codex-home"
mkdir -p "$TMP/bin" "$CODEX_HOME"

cat > "$TMP/bin/fake-codex" <<'EOF'
#!/bin/sh
set -eu
if [ "${1:-}" = "resume" ]; then
  printf '%s\n' "$*" >> "$CALL_LOG"
  exit 0
fi
count=0
if [ -f "$CODEX_HOME/session_index.jsonl" ]; then count="$(wc -l < "$CODEX_HOME/session_index.jsonl" | tr -d ' ')"; fi
id="test-session-$((count + 1))"
printf '{"id":"%s","thread_name":"test","updated_at":0}\n' "$id" >> "$CODEX_HOME/session_index.jsonl"
sleep 2
EOF
chmod +x "$TMP/bin/fake-codex"

XDG_STATE_HOME="$STATE" CODEX_HOME="$CODEX_HOME" CODEX_BIN="$TMP/bin/fake-codex" CALL_LOG="$TMP/calls" "$ROOT/bin/codex-zellij" &
first=$!
sleep 1
XDG_STATE_HOME="$STATE" CODEX_HOME="$CODEX_HOME" CODEX_BIN="$TMP/bin/fake-codex" CALL_LOG="$TMP/calls" "$ROOT/bin/codex-zellij" &
second=$!
wait "$first"
wait "$second"

set -- "$STATE/codex-zellij-resume/markers/"*
[ "$#" -eq 2 ]
first_id="$(cat "$1")"
second_id="$(cat "$2")"
[ "$first_id" != "$second_id" ]

for marker in "$STATE/codex-zellij-resume/markers/"*; do
  value="$(cat "$marker")"
  output="$(XDG_STATE_HOME="$STATE" RESURRECT_COMMAND="$ROOT/bin/codex-zellij --zellij-marker $(basename "$marker")" "$ROOT/bin/zellij-codex-resurrect")"
  [ "$output" = "codex resume $value --no-alt-screen" ]
done

printf '%s\n' 'ok'
