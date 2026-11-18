#!/usr/bin/env bash
# Daily health note (read only, no sudo). Set OUT, LOG_DIR, BACKUP_MOUNT and BACKUP_UUID (UUID of the backup drive).
: "${BACKUP_MOUNT:?set BACKUP_MOUNT}" "${BACKUP_UUID:?set BACKUP_UUID}"
out="${OUT:-$HOME/health.md}"
L="${LOG_DIR:-/var/log/homelab}"
last() { for f in "$L/$1.log" "$L/$1.log.1"; do [ -s "$f" ] && { tail -1 "$f"; return; }; done; echo "no log"; }
# Backup age from the epoch file written by backup.sh (new version).
ok=$(cat "$L/backup.last-ok" 2>/dev/null)
if [[ "$ok" =~ ^[0-9]+$ ]]; then days=$(( ($(date +%s) - ok) / 86400 )); else days=""; fi
ls "$BACKUP_MOUNT" >/dev/null 2>&1   # trigger the automount
bk=$([ "$(findmnt -n -t ext4 -o UUID "$BACKUP_MOUNT" 2>/dev/null)" = "$BACKUP_UUID" ] && echo yes || echo NO)
{
echo "# Server health $(date '+%Y-%m-%d %H:%M')"
[ -z "$days" ] && echo "ALERT backup age unknown (no last-ok record)"
[ -n "$days" ] && [ "$days" -ge 2 ] && echo "ALERT backup $days days old"
[ "$bk" = NO ] && echo "ALERT backup drive not connected"
echo "- backup status: $(cat "$L/backup.status" 2>/dev/null || echo 'no status file') (last OK: ${days:-?} days ago)"
echo "- restic backup log: $(last backup | cut -c1-140)"
echo "- vaultwarden backup: $(last backup-vaultwarden | cut -c1-140)"
echo "- backup drive mounted: $bk"
echo "- disk /: $(df -h / | awk 'NR==2{print $5" used, "$4" free"}')"
if f=$(systemctl --failed --no-legend --plain 2>/dev/null); then
  f=$(awk '{print $1}' <<<"$f" | paste -sd ' ' -); echo "- failed units: ${f:-none}"
else echo "- failed units: CHECK UNAVAILABLE (systemctl error)"; fi
if d=$(docker ps -a --format '{{.Names}}:{{.Status}}' 2>/dev/null); then
  r=$(grep -viE ':Up' <<<"$d" | paste -sd ' ' -); echo "- containers not up: ${r:-none}"
  echo "- containers up: $(grep -ciE ':Up' <<<"$d")"
else echo "- containers: CHECK UNAVAILABLE (docker error)"; fi
echo "- reboot required: $([ -f /var/run/reboot-required ] && echo yes || echo no)"
echo "- upgradable packages: $(apt list --upgradable 2>/dev/null | grep -c upgradable)"
} > "$out.tmp" && mv "$out.tmp" "$out"
