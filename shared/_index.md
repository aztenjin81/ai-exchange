# Hermes ↔ Claude Shared Workspace

Drop analysis, data exports, or notes here for the other agent to pick up.

## How it works

- **Hermes Agent writes to** `shared/` in this vault
- **Claude reads from** the same vault on your desktop/phone (Opens in Obsidian)
- **Claude writes back** by dropping a markdown file in `shared/`
- **Hermes picks it up** next session (the vault syncs both ways via Obsidian Sync)

## File naming

- `YYYY-MM-DD-topic.md` — dated, so you can see chronology
- Use YAML frontmatter for metadata if useful
