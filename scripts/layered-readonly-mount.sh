#!/bin/bash
# Layered read-only mount for a personal archive drive. Run with sudo. Reversible: see UNDO at the bottom.
# Layer 1: the archive read-write in a root-only folder (nobody browses here).
# Layer 2: read-only bind at the VIEW folder (everything the team sees).
# Layer 3: read-write bind of $WRITABLE only (Immich iPhone sync).
set -euo pipefail
RW="${RW:-/srv/data/.rw}"          # hidden read-write mount (root only)
VIEW="${VIEW:-/srv/data/archive}"  # what the agents see: read-only
UUID="${DRIVE_UUID:?set DRIVE_UUID}"
WRITABLE="${WRITABLE:-sync/library}"  # the one sub folder that stays writable
[ "$(id -u)" = 0 ] || { echo "Run with sudo"; exit 1; }
umount -R "$VIEW" 2>/dev/null || true       # remove old mounts
mountpoint -q "$RW" && umount "$RW" || true
mkdir -p "$RW"; chmod 700 "$RW"
mount -t exfat -o rw,nosuid,nodev,noexec,noatime,uid=${AGENT_UID:-1000},gid=${AGENT_GID:-1000},umask=000 UUID=$UUID "$RW"
mount --bind "$RW" "$VIEW"
mount -o remount,bind,ro "$VIEW"
mount --bind "$RW/$WRITABLE" "$VIEW/$WRITABLE"
echo "--- result"; findmnt -R "$VIEW" -o TARGET,OPTIONS | cut -c1-110
echo "--- test: delete must fail"; touch "$VIEW/.t" 2>&1 | head -1 || true
# UNDO: sudo umount -R "$VIEW"; sudo umount "$RW"
