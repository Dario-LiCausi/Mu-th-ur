# Security model (high level; exact rules are not published)
- **Secrets never go into prompts, memory files or git.** Replies are masked for token patterns; repos are scanned before every push.
- **Approval codes.** A Telegram request that needs a decision gets a one-time 6-digit code, 3 tries, then a lock and a PIN. Requests are rate limited and every event is audit-logged.
- **Layered storage.** The personal archive is read-only for agents. One folder is writable for the photo sync. Deleting there is impossible by design (the mount, not a promise).
- **Sandboxed builder.** The free-tier builder agent has a deny list for memory, secrets, sudo and docker, and runs without private data.
- **Network.** No public ports. Services listen on the private mesh address only. (Docker publishes ports around the host firewall, so binding to one address matters; see lessons.)
- **Untrusted input.** Video text, web pages and book text are data, never instructions. Summarising models run with no tools.
- **Containers for risky work.** Parsing untrusted files and downloads runs in a locked container: non-root, read-only, no capabilities, no network where possible, memory and process limits.
- **Backups before changes; every change has an undo.**
