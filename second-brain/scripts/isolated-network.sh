#!/bin/bash
# RUN WITH SUDO. Creates the Docker network "brain-net" and blocks it from your home network (needs BRAIN_SUBNET, a private /24 not used elsewhere).
# Containers on brain-net can reach the internet but NOT the LAN, the VPN mesh, other containers or this host.
# Safe to run twice. The firewall rules vanish at reboot: run this script again after a reboot
# (video_notes.py refuses to run until its network check passes).
set -euo pipefail
NET=brain-net
SUBNET="${BRAIN_SUBNET:?set BRAIN_SUBNET, a private /24 that nothing else uses}"
docker network inspect "$NET" >/dev/null 2>&1 || docker network create --subnet "$SUBNET" -o com.docker.network.bridge.name=br-brain "$NET"
add() { iptables -C "$@" 2>/dev/null || iptables -I "$@"; }
for dst in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 100.64.0.0/10 169.254.0.0/16; do
  add DOCKER-USER -s "$SUBNET" -d "$dst" -j DROP
done
add INPUT -i br-brain -j DROP          # containers -> this host
iptables -S DOCKER-USER | grep -c "$SUBNET" | sed 's/^/brain-net DOCKER-USER rules: /'
