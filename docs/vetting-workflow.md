# Vetting third-party code before use
1. **Clone, never run or install.** Note the commit.
2. **Scan:** install hooks, `curl | sh`, `eval`/`exec`, encoded blobs, hidden files, network targets (`scripts/vet-repo.sh`).
   - **Hooks and install commands:** `scripts/hook-risk.py <folder>` reads settings files, plugin manifests, git hooks, package install scripts and the hooks declared in a skill's own header. A skill that registers a hook runs code on every event, so it is rejected unless the owner decides otherwise.
   - **Skills:** `scripts/skill-scan.sh <folder> <skill>` runs a static security scanner (NVIDIA SkillSpector) in a container with no network, a read-only file system and no model calls. Treat the score as a reading list, not a verdict: text about security triggers it.
   - **Read the text yourself.** A skill is instructions. Look for hidden or invisible characters, "ignore previous" phrases, downloads and anything that widens its own permissions.
3. **Several agents review** independently (builder, second reviewer, attacker).
4. **Sync gate:** wait for every reviewer. A silent reviewer is a reported gap, not a pass.
5. **One-line report per reviewer, one question for the owner.** The owner approves.
6. **Install only the vetted files**, smallest scope first (plain text skills before hooks or servers). Log it with an undo line.
Pin versions with hashes and use a cooldown (nothing newer than about two weeks) for packages.
7. **Never use files offered in a private message** ("comment to get the skills"). Use the public repository only, cloned into an empty folder.
8. **Edit before install, and say so.** If a skill tells the agent to download things, change that line and add a short "local rules" section (fonts and assets stay local, no network while rendering). Record the hash of the original and of the edited file.
