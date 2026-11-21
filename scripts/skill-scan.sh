#!/usr/bin/env bash
# skill-scan.sh <folder> [skill-subfolder]: static security scan of an agent skill with NVIDIA SkillSpector.
# Runs in Docker image skillspector:local (built from , hash-pinned deps) with
# NO network, read-only root, all capabilities dropped, folder mounted read-only, --no-llm (static only).
# Never uses an LLM or an API key. A second opinion next to scripts/hook-risk.py, not a replacement.
# Exit: 0 = SAFE or LOW, 1 = issues or a recommendation other than SAFE, 2 = usage or setup error.
set -u
D="${1:-}"; S="${2:-.}"
[ -d "$D" ] || { echo "usage: skill-scan.sh <folder> [skill-subfolder]"; exit 2; }
docker image inspect skillspector:local >/dev/null 2>&1 || { echo "image skillspector:local missing: docker build -t skillspector:local -f <build dir>/Dockerfile <build dir>/ctx  (a Dockerfile that installs NVIDIA SkillSpector from its hash-pinned lock file)"; exit 2; }
OUT=$(mktemp); trap 'rm -f "$OUT"' EXIT
timeout "${SKILL_SCAN_TIMEOUT:-600}" docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --tmpfs /tmp --tmpfs "/home/${SCANNER_USER:-scanner}" \
  -v "$(cd "$D" && pwd)":/scan:ro skillspector:local scan "$S" --no-llm --format json > "$OUT" 2>/dev/null
rc=$?
[ "$rc" = 124 ] && { echo "skill-scan: timeout after ${SKILL_SCAN_TIMEOUT:-600}s (big skill: raise SKILL_SCAN_TIMEOUT)"; exit 2; }
python3 -I - "$OUT" "$D/$S" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print("skill-scan: no JSON result (scan failed)"); sys.exit(2)
r, c = d["risk_assessment"], d["analysis_completeness"]
print(f"skill-scan {sys.argv[2]}: score {r['score']} {r['severity']} -> {r['recommendation']} | coverage {c['coverage_percent']}% ({c['status']}) | issues {len(d['issues'])}")
for x in d["issues"][:25]:
    loc = x.get("location") or {}
    print(f"  {x.get('severity')} {x.get('category')}/{x.get('pattern')} {loc.get('file')}:{loc.get('start_line')} | {str(x.get('finding'))[:80]}")
sys.exit(0 if r["recommendation"] == "SAFE" else 1)
PY
