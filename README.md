# Hermes Vault

A two-tier knowledge system: **memory** holds high-frequency response-shaping facts, **this vault** holds everything else.

## Agent Rules

1. **Frontmatter is required** on every note — `type`, `status`, `date` minimum
2. **Use wikilinks** `[[Note Name]]` for internal references, not markdown `[]()` links
3. **Link liberally** between related notes — the graph is the navigation
4. **Folder structure is fixed** — do not create/delete/rename top-level folders
5. **New notes** go in the appropriate folder, use a template from `Templates/`
6. **Session logs** go in `Logs/` with date prefix: `YYYY-MM-DD-topic.md`
7. **Archive** is for dead/old/replaced notes — move don't delete
8. **Do NOT** edit `.obsidian/` config files unless explicitly asked
9. **Do NOT** add emojis or editorialize in reference notes — stay factual
10. **Revert** the `ob sync` after any batch of vault writes

## Vault Map

| Folder | Contents |
|--------|----------|
| `Reference/` | Stable facts — family, food, infra, work style |
| `Automation/` | Cron jobs, .base inventories, monitoring configs |
| `Logs/` | Per-session output, decisions, deferred tasks |
| `Templates/` | Reusable note templates with frontmatter |
| `Archive/` | Replaced/obsolete notes — never delete |

## Status Values

- `active` — current, accurate
- `draft` — in progress, not yet reliable
- `archived` — replaced or obsolete
- `stale` — may be out of date, needs review

## Notes

- Created 2026-05-16 by Hermes agent
- Synced via Obsidian Sync (headless CLI)
- All times America/Phoenix (MST, UTC-7) unless noted
