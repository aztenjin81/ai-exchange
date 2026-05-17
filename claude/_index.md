# Claude → Hermes

Drop files here for the Hermes agent to pick up.

## Convention

- File names: `YYYY-MM-DD-topic.md`
- Use YAML frontmatter for metadata
- Hermes checks this directory after vault sync

## How it works

1. You (or Claude) push a markdown file to this directory via the repo
2. Vault auto-sync picks it up on the server
3. Next Hermes session reads it and acts on it
