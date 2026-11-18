#!/bin/bash
# Vet third-party code BEFORE use. Never runs or installs the code.
# Usage: vet-repo.sh <git-url> [sha-or-tag]   (clones into work/vet/<name>)
#        vet-repo.sh --dir <path>             (scan an existing local folder)
set -uo pipefail
if [ "${1:-}" = "--dir" ]; then D="$2"; else
  URL="$1"; REF="${2:-}"; N="$(basename "$URL" .git)"; D="${VET_DIR:-$HOME/vet}/$N"
  [ -e "$D" ] && { echo "exists: $D (delete it first)"; exit 2; }
  mkdir -p "${VET_DIR:-$HOME/vet}"
  GIT_TERMINAL_PROMPT=0 git clone -q --no-recurse-submodules "$URL" "$D" || exit 2
  [ -n "$REF" ] && git -C "$D" checkout -q "$REF"
  echo "== commit: $(git -C "$D" rev-parse HEAD)  ($(git -C "$D" log -1 --format=%cd --date=short))"
  echo "== commits: $(git -C "$D" rev-list --count HEAD)  authors: $(git -C "$D" log --format=%an | sort -u | wc -l)"
  echo "== submodules: $(git -C "$D" ls-files --stage | grep -c '^160000')"
fi
cd "$D" || exit 2
X=(-not -path './.git/*')
echo "== size/files: $(find . "${X[@]}" -type f | wc -l) files, $(du -sh --exclude=.git . | cut -f1)"
echo "== binaries / archives / compiled (should be none):"
find . "${X[@]}" -type f \( -name '*.exe' -o -name '*.dll' -o -name '*.so' -o -name '*.dylib' -o -name '*.bin' -o -name '*.pyc' -o -name '*.jar' -o -name '*.zip' -o -name '*.tar*' -o -name '*.wasm' \) | head -20
find . "${X[@]}" -type f -exec file {} + 2>/dev/null | grep -E 'ELF|Mach-O|PE32|executable' | grep -v 'script' | head -10
echo "== install/lifecycle hooks and entry points:"
find . "${X[@]}" -type f \( -name 'package.json' -o -name 'setup.py' -o -name 'pyproject.toml' -o -name 'Makefile' -o -name 'Dockerfile*' -o -name 'docker-compose*' -o -name 'hooks.json' -o -name 'plugin.json' -o -name '*.sh' \) | head -40
grep -rEn '"(pre|post)?install"|"prepare"|"postinstall"|cmdclass|"hooks"|SessionStart|UserPromptSubmit|PreToolUse|PostToolUse' . --include=package.json --include=setup.py --include=*.json --include=*.toml 2>/dev/null | grep -v node_modules | head -20
echo "== dangerous patterns (file:line):"
P='eval\(|exec\(|os\.system|subprocess|child_process|Function\(|curl[^|]*\|\s*(ba)?sh|wget[^|]*\|\s*(ba)?sh|base64 -d|base64\.b64decode|atob\(|fromCharCode|\\x[0-9a-f]{2}\\x[0-9a-f]{2}|bash -i|/dev/tcp|nc -e|rm -rf|chmod \+x|crontab|authorized_keys|\.ssh|\.aws|\.env|API_KEY|SECRET|TOKEN|PASSWORD|keychain|/etc/passwd|sudo '
grep -rEIn "$P" . --exclude-dir=.git --exclude-dir=node_modules 2>/dev/null | cut -c1-170 | head -80
echo "== network targets (urls/ips, unique):"
grep -rEIoh 'https?://[A-Za-z0-9./_?=&%:#~-]+|[0-9]{1,3}(\.[0-9]{1,3}){3}' . --exclude-dir=.git --exclude-dir=node_modules 2>/dev/null | sed -E 's#(https?://[^/]+).*#\1#' | sort | uniq -c | sort -rn | head -25
echo "== long encoded blobs (>200 chars no spaces):"
grep -rEIn '[A-Za-z0-9+/=]{200,}' . --exclude-dir=.git --exclude-dir=node_modules --exclude=*.lock --exclude=package-lock.json 2>/dev/null | cut -c1-120 | head -10
echo "== hidden files:"; find . -name '.*' -not -name .git -not -name . -not -path './.git/*' | head -15
echo "== dependencies:"; for f in package.json requirements*.txt pyproject.toml go.mod Cargo.toml; do [ -f "$f" ] && { echo "-- $f"; grep -E '"[a-z@/._-]+": *"[~^0-9*><=]|^[a-zA-Z0-9_.-]+(==|>=|~=)' "$f" | head -30; }; done
echo "== done (report only; read the hits yourself)"
