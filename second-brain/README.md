# Second brain (a Telegram-first assistant for people who forget things)

Built for one person with ADHD: forgetting, overstimulation, a pile of saved videos that never get watched.
Everything is self-hosted, plain files plus SQLite, and every piece of untrusted content is handled as **data**.

```
 share a link / book ──> inbox (Telegram) ──> job queue ──> locked container (yt-dlp, Whisper, OCR; no secrets)
                                                 │                    │
        07:20 / 17:00 nudge  <── brain_nudge ────┘            notes + transcripts + search index (SQLite FTS5)
```

## Modules
| Folder | What it does | Tests |
|---|---|---|
| `nudge/` | One message per slot (morning, evening on work days, Sunday triage), quiet hours, pause/resume, no repeat after a restart, no list longer than 3 | 18 |
| `video-notes/` | A shared video link becomes a note: YouTube captions, or audio + local Whisper; summary by a model **without tools**; for videos about AI, a sceptical critique with a verdict that only ever *proposes* | 26 |
| `library/` | Books and documents become searchable text: PDF, EPUB, DjVu, HTML; OCR for scans; answers cite book and page; nothing leaves the machine | 21 |
| `watch/` | Watches one folder (read only) for new books, copies finished files, indexes them, tells you; never overwrites | 12 |
| `worker/` | Docker images for the risky work: non-root, read-only, no capabilities, hash-pinned packages, pinned model | |
| `scripts/isolated-network.sh` | A Docker network that can reach the internet but not your home network | |

## How it handles untrusted input
- Video titles, transcripts and book text are **data**. The summariser and critic run with no tools and no credentials.
- Downloads and parsing run in a locked container: caps on duration, size and pages; one job at a time; temporary audio is deleted after every job.
- A job that fails twice is marked, not retried forever. A bad job file cannot block the queue.
- Notes are written atomically and re-read right before writing, so edits you make while a slow job runs survive.
- Model output is neutralised (no markdown links or tags), and the verdict only counts from a clean first line.
- Nothing is ever deleted: dropped items are archived.

## Settings (environment variables, no config files)
`BRAIN_HOME` (default `~/second-brain`), `BRAIN_SUBNET` (a private /24 for the isolated network), `BRAIN_WORKER_DIR`, `WATCH_SRC` (folder to watch).
Build the images from `worker/` (`Dockerfile`, `Dockerfile.library`). Cron examples:
```
*/10 * * * *  python3 video-notes/video_notes.py run
0 3 * * *     python3 library/library.py sync
*/30 * * * *  python3 watch/folder_watch.py run
```

## Run the tests
```bash
for d in nudge video-notes library watch; do (cd $d && BRAIN_HOME=/tmp/sb python3 -m unittest discover -p 'test_*.py'); done
```
77 tests; they use fake Docker and fake model commands, so no containers or models are needed.

## Honest status
This is a working personal system, extracted from a larger private one. The Telegram relay with approval codes and the inbox commands are not included yet.
Whisper on a laptop CPU is slow (minutes per video). Instagram works only for public reels, with no login stored. The code was written with AI coding agents
under my direction, reviewed by an independent second agent, and covered by tests; I am still learning to read and change every part of it myself.
