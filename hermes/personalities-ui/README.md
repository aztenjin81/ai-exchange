# Hermes Personalities UI

A web interface for managing multiple Hermes agent personalities — personality CRUD, provider management, MCP server assignment, cron jobs, workflow pipelines, and token usage tracking.

## Quickstart

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Health check: http://localhost:8000/health

## Stack

- **Backend:** Python 3.11 / FastAPI / aiosqlite
- **Frontend:** SvelteKit 5 / Tailwind CSS v4
- **Config:** YAML via ruamel.yaml (preserves comments)
- **DB:** SQLite (WAL mode)

## Project Structure

```
personalities-ui/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── models/          # Pydantic schemas
│       ├── routers/         # API routes
│       ├── services/        # Business logic
│       └── websocket/       # WS handlers
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── src/
        ├── app.html
        ├── app.css
        ├── lib/
        │   ├── api/         # API client + WS
        │   ├── stores/      # Svelte stores
        │   └── components/  # Reusable UI
        └── routes/          # Pages
```

## Docs

See the `docs/` directory for architecture reference and build plan:

- `Reference/Hermes-Personalities-UI.md` — Full architecture document
- `BUILD.md` — Executable build plan for AI agents

## Migrating from CLI

On first boot, the UI scans `~/.hermes/config.yaml`, profiles, and cron DB, then presents an inventory screen. You can selectively import providers, MCP servers, and personalities. Everything continues to work both via CLI and UI — they share the same config files.
