#!/bin/bash
# The agent's only door to the file server: inbox (read) and outbox (write).
# Usage: nc.sh in-list [subfolder] | in-get <name or subfolder/name> | out-list | out-put <file> [name] [subfolder] | out-mv <path> <newpath>
set -euo pipefail
C="${NC_CONTAINER:-nextcloud}"
ROOT="${NC_ROOT:?set NC_ROOT, e.g. /var/www/html/data/USER/files/AGENT}"
IN="$ROOT/inbox"; OUT="$ROOT/outbox"
SCAN="${NC_SCAN:?set NC_SCAN, e.g. USER/files/AGENT}"
MAXMB=50
MAXMB_IN=700   # reading books from inbox: same limit as the library (700 MB)
bad() { echo "REFUSED: $*" >&2; exit 2; }
okname() { [[ -n "$1" && "$1" != .* && "$1" != */* && ${#1} -le 200 && "$1" != *$'\n'* ]] || bad "bad file name"; }
case "${1:-}" in
  in-list)  # in-list [subfolder]  (one level only)
    SUB="${2:-}"; DIR="$IN"
    if [ -n "$SUB" ]; then okname "$SUB"; docker exec -u www-data $C sh -c 'test -d "$1" && ! test -L "$1"' _ "$IN/$SUB" || bad "not a folder in inbox"; DIR="$IN/$SUB"; fi
    docker exec -u www-data $C ls -lA "$DIR" ;;
  out-list) docker exec -u www-data $C ls -lA "$OUT" ;;
  in-get)
    # in-get <name> | in-get <subfolder>/<name>   (one subfolder level)
    R="${2:-}"; SUB=""; N="$R"
    if [[ "$R" == */* ]]; then SUB="${R%%/*}"; N="${R#*/}"; okname "$SUB"; docker exec -u www-data $C sh -c 'test -d "$1" && ! test -L "$1"' _ "$IN/$SUB" || bad "not a folder in inbox"; fi
    okname "$N"
    SRC="$IN${SUB:+/$SUB}/$N"
    docker exec -u www-data $C sh -c 'test -f "$1" && ! test -L "$1"' _ "$SRC" || bad "not a regular file in inbox"
    docker exec -u www-data $C sh -c '[ "$(stat -c %s "$1")" -le $(( $2 * 1048576 )) ]' _ "$SRC" "$MAXMB_IN" || bad "file over ${MAXMB_IN} MB"
    DD="${LOCAL_DROP:-$HOME/drop}${SUB:+/$SUB}"; mkdir -p "$DD"
    D="$DD/$N"; [ ! -e "$D" ] || bad "already exists: $D"
    docker cp "$C:$SRC" "$D"; echo "$D" ;;
  out-put)
    S="${2:-}"; [ -f "$S" ] && [ ! -L "$S" ] || bad "source is not a regular file"
    [ "$(stat -c %s "$S")" -le $((MAXMB*1048576)) ] || bad "file over ${MAXMB} MB"
    N="${3:-$(basename "$S")}"; okname "$N"
    SUB="${4:-}"; DEST="$OUT"
    if [ -n "$SUB" ]; then okname "$SUB"; DEST="$OUT/$SUB"; docker exec -u www-data $C mkdir -p "$DEST"; fi
    docker exec -u www-data $C sh -c '! test -e "$1"' _ "$DEST/$N" || bad "exists in outbox (no overwrite)"
    T="/tmp/nc-up-$$"
    docker cp "$S" "$C:$T"
    docker exec -u root $C sh -c 'chown www-data:www-data "$1" && chmod 640 "$1" && mv -n "$1" "$2"' _ "$T" "$DEST/$N"
    docker exec -u www-data $C php occ files:scan --path="$SCAN/outbox" >/dev/null
    echo "OK: outbox/${SUB:+$SUB/}$N" ;;
  out-mv)
    # Move or rename INSIDE outbox only. No overwrite. Relative paths, no "..".
    A="${2:-}"; B="${3:-}"
    for P in "$A" "$B"; do
      [[ -n "$P" && "$P" != /* && "$P" != *..* && "$P" != *$'\n'* && ${#P} -le 300 ]] || bad "bad path"
    done
    docker exec -u www-data $C sh -c 'test -e "$1" && ! test -L "$1"' _ "$OUT/$A" || bad "source missing or a link"
    docker exec -u www-data $C sh -c '! test -e "$1"' _ "$OUT/$B" || bad "target exists (no overwrite)"
    docker exec -u www-data $C sh -c 'mkdir -p "$(dirname "$2")" && mv -n "$1" "$2"' _ "$OUT/$A" "$OUT/$B"
    docker exec -u www-data $C php occ files:scan --path="$SCAN/outbox" >/dev/null
    echo "OK: moved outbox/$A -> $B" ;;
  *) echo "Usage: nc.sh in-list | in-get <name> | out-list | out-put <file> [name] [subfolder] | out-mv <path> <newpath>" >&2; exit 2 ;;
esac
