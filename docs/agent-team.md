# The agent team
| Role | Tool (model) | Job | Limits |
|---|---|---|---|
| **Odin** | Claude Code | Plans, splits tasks, integrates, approves | Works inside the project folder; asks before irreversible steps |
| **Hawk** | OpenCode (free model) | Heavy building and first drafts | Sandboxed: no private data, no memory files, no sudo, no docker |
| **Merlin** | Codex | Reviews and attacks every change | Reads pasted content; finds bugs and security holes |
| **Andromeda** | Gemini (free tier) | Second reviewer for public text | Public text only |
| **Flora** | Small local model | Tiny text jobs | Output always checked |
Rules: one task, several roles; **sync gate** (wait until every role has reported before moving on); a task is not done until it has tests, a review and a log entry; the owner decides on installs and publishing.
The agents share a written memory (decisions, change log with undo lines, to-do list) so a new session can continue without guessing.
