---
type: log
status: draft
date: 2026-05-16
tags: [session, obsidian, vault-setup]
---

# 2026-05-16 — Obsidian Vault Setup & Memory Optimization

## What was done

- Created vault at ~/hermes-vault with folder structure (Reference/, Automation/, Logs/, Templates/, Archive/)
- Wrote orientation contract (README.md) defining vault rules for the agent
- Migrated low-frequency memory data (family, food, infra, work style) from hot memory to vault
- Created individual server notes for all VMs/CTs with proper YAML frontmatter
- Created .base view files (Servers.base) for queryable views
- Installed Obsidian .deb natively on DevServer
- Set up Obsidian Headless CLI (`ob`) for sync
- Created Obsidian Sync remote vault "Hermes Vault" and linked local path
- Pushed all vault files to Obsidian Sync
- Set up cron job for every-15-minute auto-sync
- Trimmed memory from ~2,288 chars to ~1,014 chars (-56%)

## Decisions

- Using Obsidian Sync (paid) over Syncthing — simpler, purpose-built
- Flat folder structure with shallow categorization over numbered PARA
- .base files for structured views over individual per-record files
- Frontmatter on every note — `type`, `status`, `date` minimum

## Deferred

- Clean up Syncthing service / config (currently unused)
- Add individual Cron .base view
- Investigate full Obsidian CLI features for vault management

## Next

- Implement session log pattern for future work
- Continue populating infrastructure notes
