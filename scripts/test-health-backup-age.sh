#!/usr/bin/env bash
# Tests the backup-age alarm of scripts/health.sh with fake log folders (no root, no real logs).
# Run: bash scripts/test-health-backup-age.sh      Result: "all ok", or FAIL lines and exit 1.
# Prove the test can fail: HEALTH_SCRIPT=/path/to/a/broken/copy bash scripts/test-health-backup-age.sh
set -u
H="${HEALTH_SCRIPT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/health.sh}"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
fails=0
run() { OUT="$T/out.md" LOG_DIR="$1" BACKUP_MOUNT="$T" BACKUP_UUID=none bash "$H" >/dev/null 2>&1; cat "$T/out.md"; }
expect() { # name, text that must be in the output, text that must not be (optional)
  grep -qF -- "$2" <<<"$OUT" || { echo "FAIL $1: missing '$2'"; fails=$((fails+1)); }
  if [ -n "${3:-}" ] && grep -qF -- "$3" <<<"$OUT"; then echo "FAIL $1: should not contain '$3'"; fails=$((fails+1)); fi
}
mk() { D="$T/$1"; mkdir "$D"; }
mk d1; echo "snapshot 5b5b714f saved" > "$D/backup.log"
OUT=$(run "$D"); expect "fresh log" "(from backup log time)" "ALERT backup age"
mk d2; echo "snapshot 5b5b714f saved" > "$D/backup.log"; touch -d '3 days ago' "$D/backup.log"
OUT=$(run "$D"); expect "old log" "ALERT backup 3 days old"
mk d3; echo "Fatal: repository is already locked" > "$D/backup.log"
OUT=$(run "$D"); expect "error log" "ALERT backup age unknown"
mk d4
OUT=$(run "$D"); expect "no log" "ALERT backup age unknown"
mk d5; echo "snapshot 5b5b714f saved" > "$D/backup.log"; touch -d '5 days ago' "$D/backup.log"; date +%s > "$D/backup.last-ok"
OUT=$(run "$D"); expect "last-ok file wins" "last OK: 0 days ago" "from backup log time"
mk d6; : > "$D/backup.log"; echo "snapshot 5b5b714f saved" > "$D/backup.log.1"
OUT=$(run "$D"); expect "rotated log" "(from backup log time)" "ALERT backup age"
[ "$fails" -eq 0 ] && echo "all ok" || { echo "$fails failure(s)"; exit 1; }
