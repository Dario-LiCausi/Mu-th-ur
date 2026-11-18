# Lessons learned (real incidents)
1. **Docker bypasses the host firewall.** Published container ports ignored the firewall rules. Fix: bind services to the private mesh address only, and test from another device.
2. **Cron has a tiny PATH.** A scheduled agent job failed silently because `claude` was not on cron's PATH. Fix: set PATH in the script; check the log after the first scheduled run.
3. **`pgrep -f` can match its own parent shell.** Three chained scripts waited forever on each other's names while an agent sat idle for hours. Fix: wait on a marker file or a PID.
4. **Unpinned dependencies break in pairs.** A newer media library removed an argument that the transcription package still passed. Fix: hash-pinned requirements with a version cap, and a live test of the real file type.
5. **Free models are fast but need review.** The builder agent's work always went through a second reviewer; the reviewer found real bugs every round (path traversal, race conditions, stale state, rounding).
6. **Scanned books have no text.** A search index looked complete but half the files were images. Fix: report "needs OCR" instead of "indexed", then run OCR in a locked container.
7. **Names that leak.** A public repo build must scrub internal host names, drive IDs and personal names. Fix: an automated scan that fails the build.
8. **Ask, then act, with limits.** Delegated work got a cost cap, a time limit and an undo line each time.
