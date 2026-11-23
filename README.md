# Thalamus + MU/TH/UR: a private home server run with a team of AI agents

A single home server ("Thalamus") that hosts my files, photos and passwords, and a small team of AI coding agents
("MU/TH/UR") that plan, build, review and operate it, with human approval gates and security rules.
Everything here is documentation and sanitised example scripts. No secrets, addresses or personal data.

> **How this was made.** I designed and operate the system. The scripts and documents were written with AI coding agents
> (Claude Code, OpenCode, Codex) under my direction, and checked by a second, independent agent plus automated tests.
> I am learning to read and change the code myself. (Owner: edit this paragraph to your own words.)

## What is in it
| Part | What | Where |
|---|---|---|
| Server | One Ubuntu machine, Docker services, a private VPN mesh for remote access, nightly backups, a daily health note | `docs/architecture.md`, `docs/operations.md` |
| Agent team | Planner, builder, reviewer, second reviewer, tiny local model. Each has a role and limits | `docs/agent-team.md` |
| Security model | Least privilege, approval codes, read-only data layers, vet-before-install | `docs/security-model.md` |
| Vetting workflow | How third-party code is checked by several agents before anything is installed | `docs/vetting-workflow.md` |
| Lessons learned | Real mistakes and how they were fixed | `docs/lessons-learned.md` |
| Example scripts | Health check (with a test for its backup alarm), layered read-only mount, vetting scan, hook and skill scanners, a controlled door to a file server | `scripts/` |
| **Second brain** | A Telegram-first assistant: nudges, video notes, a searchable library (77 tests) | `second-brain/` |

## Design principles
1. **Humans approve what matters.** Installs, deletions, publishing and anything irreversible need a yes.
2. **Least privilege.** Each agent sees only what its job needs. The weakest agent never sees private data.
3. **Read-only by default.** Personal archives are mounted read-only for agents; there is one writable exception.
4. **Verify, never trust.** Third-party code is cloned, scanned and reviewed before use. Model output is untrusted text.
5. **Everything is logged and reversible.** Every change has a backup and an undo line.

## Related
The small local-model helper with approval-based memory is a separate repo: [flora](https://github.com/Dario-LiCausi/flora).

## Licence
MIT. See `LICENSE`.
