#!/bin/bash
# Layered read-only mount for a personal archive drive. Run with sudo. Reversible: see UNDO at the bottom.
# Layer 1: the drive mounted READ-WRITE inside a ROOT-ONLY parent folder. Ordinary users cannot even walk into the parent,
#          so the permissions of the mounted drive do not matter (a chmod on a mount point is hidden once the drive is mounted).
# Layer 2: a read-only bind of the whole drive: this is what the agents see.
# Layer 3: a read-write bind of ONE sub folder (for example a photo sync folder) that a service must write to.
set -euo pipefail
PARENT="${PARENT:-/srv/.archive-private}"     # root:root, mode 700
RW="$PARENT/rw"
VIEW="${VIEW:-/srv/data/archive}"             # what the agents see: read-only
UUID="${DRIVE_UUID:?set DRIVE_UUID}"
WRITABLE="${WRITABLE:-sync/library}"          # the one sub folder that stays writable
MASK="${MASK:-fmask=0133,dmask=0022}"         # use umask=000 ONLY if the writable folder is written by a different user id
[ "$(id -u)" = 0 ] || { echo "Run with sudo"; exit 1; }
umount -R "$VIEW" 2>/dev/null || true         # remove old mounts
mountpoint -q "$RW" && umount "$RW" || true
mkdir -p "$PARENT" "$VIEW"; chown root:root "$PARENT"; chmod 700 "$PARENT"; mkdir -p "$RW"
mount -t exfat -o "rw,nosuid,nodev,noexec,noatime,uid=${AGENT_UID:-1000},gid=${AGENT_GID:-1000},$MASK" UUID="$UUID" "$RW"
mount --bind "$RW" "$VIEW"
mount -o remount,bind,ro "$VIEW"
mount --bind "$RW/$WRITABLE" "$VIEW/$WRITABLE"
echo "--- result"; findmnt -R "$VIEW" -o TARGET,OPTIONS | cut -c1-110
echo "--- tests (all must fail for a normal user):"
touch "$VIEW/.t" 2>&1 | head -1 || true; sudo -u "${SUDO_USER:-nobody}" ls "$RW" 2>&1 | head -1 || true
# UNDO: sudo umount -R "$VIEW"; sudo umount "$RW"
