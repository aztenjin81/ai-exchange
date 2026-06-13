---
type: log
date: 2026-06-13
tags: [hermes, web-ui, planning, personalities, mcp, token-tracking, llm-management]
status: complete
---

# Session: Hermes Personalities UI — Architecture Planning

**Participants:** tenjin, hermes

## What we did

Planned and documented a web UI that works like Open WebUI but switches entire Hermes agent personalities (model, provider, system prompt, skills, toolset, memory) instead of just models.

### Key decisions

**Architecture:** FastAPI backend + SvelteKit frontend. Hermes runs in SDK mode (imported in-process) with the streaming bridge capturing the agent loop's internal events and piping them over WebSocket.

**MCP Management:** A first-class server manager that owns MCP connections independently from Hermes' global `config.yaml`. Per-personality MCP assignment with reference-counted shared connections. Tool schema caching to avoid re-discovery overhead. Health monitor with exponential backoff reconnect.

**Token Tracking:** Added as a cross-cutting component — Token Tracker sits between the Streaming Bridge and Hermes SDK. Captures per-call usage metadata from every LLM call in the agent loop, computes cost from a built-in pricing table, enforces configurable monthly budgets per personality, and exposes usage data via API and UI.

**LLM Provider Management:** Added as a self-contained backend component. Manages provider configs (OpenRouter, Anthropic, OpenCode, custom endpoints, etc.) independently from Hermes' `config.yaml`. Encrypted credential storage with pool/key rotation support. Model discovery via `GET /v1/models` per provider. Auxiliary task provider mapping grid. Per-personality provider/model assignment replaces CLI-based `hermes model` and `hermes config set`.

### Components defined

| Component | Role |
|-----------|------|
| FastAPI Server | REST + WebSocket endpoints |
| Personality Manager | Config CRUD, session routing |
| MCP Server Manager | Connection pool, lifecycle, tool injection |
| Token Tracker | Usage capture, cost calc, budget enforcement |
| LLM Provider Manager | Provider CRUD, credential mgmt, model discovery, auxiliary mapping |
| Streaming Bridge | Agent loop → WebSocket event stream |
| Frontend | SvelteKit SPA with chat, sidebar, config editor, MCP view, dashboard, provider manager |

### Key open challenges identified

- Hermes doesn't expose a streaming API — need to patch `AgentRunner` for SDK mode or build a persistent subprocess bridge
- Session isolation across N concurrent personalities is costly (N × context window)
- MCP hot-reload gap — Hermes doesn't support adding MCP servers at runtime
- Token tracking has hidden complexity: multi-turn costs, provider reporting inconsistency, pricing changes over time, budget race conditions
- Provider credential security — API keys need per-provider encrypted storage, masked UI display, pool rotation, and must never leak into logs or error messages
- Provider diversity — 20+ providers with different auth flows (static keys, OAuth, env-var references), base URL patterns, and model discovery API formats

### Implementation plan

| Phase | Duration | Core deliverables |
|-------|----------|-------------------|
| 1 — Skeleton | 1-2 days | FastAPI + WebSocket + single personality streaming |
| 2 — Multi-PM + MCP + Providers | 4-6 days | Personality CRUD, MCP manager, Provider manager, Token DB + capture |
| 3 — UX Polish | 2-3 days | Tool rendering, hotkeys, MCP view, provider model browser, token badges |
| 4 — Advanced Views | 2-3 days | Side-by-side/chain/arena, usage dashboard, budget enforcement, provider credential pools, auxiliary mapping |
| 5 — Production | 2-3 days | Auth, Docker, cost export, budget alerting, provider health monitoring |

### Documents created/updated

- `Reference/Hermes-Personalities-UI.md` — full architecture doc covering all 6 backend components, frontend views, SQLite schema, 14 open questions, and 5-phase implementation plan
- `Reference/Hermes-Profiles.md` — background on Hermes profile system (updated wikilink)
- `Logs/2026-06-13-hermes-personalities-ui-planning.md` — this file
