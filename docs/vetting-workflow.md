# Vetting third-party code before use
1. **Clone, never run or install.** Note the commit.
2. **Scan:** install hooks, `curl | sh`, `eval`/`exec`, encoded blobs, hidden files, network targets (`scripts/vet-repo.sh`).
3. **Several agents review** independently (builder, second reviewer, attacker).
4. **Sync gate:** wait for every reviewer. A silent reviewer is a reported gap, not a pass.
5. **One-line report per reviewer, one question for the owner.** The owner approves.
6. **Install only the vetted files**, smallest scope first (plain text skills before hooks or servers). Log it with an undo line.
Pin versions with hashes and use a cooldown (nothing newer than about two weeks) for packages.
