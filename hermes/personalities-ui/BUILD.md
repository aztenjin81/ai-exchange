# Hermes Personalities UI — Build Plan

Read `Reference/Hermes-Personalities-UI.md` first for architecture context. Then execute these phases in order. Each phase produces a working, testable artifact. Do not skip phases.

## Stack (pinned)

| Layer | Choice | Reason |
|---|---|---|
| Backend | Python 3.11+ / FastAPI | Lightweight async, built-in WebSocket support |
| Frontend | Svelte 5 / SvelteKit | Compile-to-JS, low overhead, good SSE support |
| CSS | Tailwind CSS v4 | Rapid prototyping, no opinionated component lib |
| DB | SQLite via aiosqlite | Zero-setup, single file per server instance |
| Config | YAML via ruamel.yaml | Preserves comments on round-trip |
| Auth | API key (simple), OAuth2 (future) | Start simple |
| Container | Docker Compose | Single `docker compose up` to run everything |

## Phase 0 — Project Skeleton

Goal: A `docker compose up` that boots both services and shows "Hello from Hermes UI."

**Files to create:**

```
personalities-ui/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app, CORS, lifespan
│   │   ├── config.py            # Pydantic settings from env vars
│   │   ├── database.py          # aiosqlite connection manager
│   │   ├── models/              # Pydantic models
│   │   │   ├── __init__.py
│   │   │   ├── personality.py
│   │   │   ├── mcp_server.py
│   │   │   ├── cron_job.py
│   │   │   ├── provider.py
│   │   │   └── token_usage.py
│   │   ├── routers/             # API routes
│   │   │   ├── __init__.py
│   │   │   ├── personalities.py
│   │   │   ├── mcp.py
│   │   │   ├── providers.py
│   │   │   ├── cron.py
│   │   │   ├── workflows.py
│   │   │   ├── sessions.py
│   │   │   └── usage.py
│   │   ├── services/            # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── personality_manager.py
│   │   │   ├── mcp_manager.py
│   │   │   ├── streaming_bridge.py
│   │   │   ├── token_tracker.py
│   │   │   ├── provider_manager.py
│   │   │   ├── cron_scheduler.py
│   │   │   ├── workflow_engine.py
│   │   │   └── migration.py     # Config.yaml sync
│   │   └── websocket/           # WS handlers
│   │       ├── __init__.py
│   │       └── handler.py
│   └── tests/
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── svelte.config.js
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── app.html
│   │   ├── app.css
│   │   ├── lib/
│   │   │   ├── api/             # API client + WebSocket
│   │   │   │   ├── client.ts
│   │   │   │   └── websocket.ts
│   │   │   ├── stores/          # Svelte stores
│   │   │   │   ├── personality.ts
│   │   │   │   ├── session.ts
│   │   │   │   ├── mcp.ts
│   │   │   │   ├── cron.ts
│   │   │   │   ├── providers.ts
│   │   │   │   └── usage.ts
│   │   │   ├── types.ts         # Shared TS types
│   │   │   └── components/      # Reusable UI
│   │   │       ├── Sidebar.svelte
│   │   │       ├── ChatView.svelte
│   │   │       ├── MessageBubble.svelte
│   │   │       ├── ToolCall.svelte
│   │   │       ├── ThinkingIndicator.svelte
│   │   │       └── TokenBadge.svelte
│   │   └── routes/
│   │       ├── +layout.svelte
│   │       ├── +page.svelte
│   │       ├── personalities/
│   │       │   ├── +page.svelte
│   │       │   └── [id]/
│   │       │       └── +page.svelte
│   │       ├── mcp/
│   │       │   └── +page.svelte
│   │       ├── providers/
│   │       │   └── +page.svelte
│   │       ├── cron/
│   │       │   └── +page.svelte
│   │       ├── workflow/
│   │       │   └── +page.svelte
│   │       └── settings/
│   │           └── +page.svelte
│   └── static/
└── README.md                    # Project overview + quickstart
```

**Verification:** `docker compose up --build` → backend responds `GET /health → {"status":"ok"}` → frontend loads at `http://localhost:5173` with "Hermes Personalities UI" title and no errors.

## Phase 1 — Personality CRUD + Chat MVP (2-3 days)

Goal: Create/manage personalities in the UI, send a message, see a simulated response.

### Backend

1. **`database.py`** — aiosqlite init, migration runner, get_db dependency. Create tables for `personalities`, `sessions`, `messages`.
2. **`models/personality.py`** — Pydantic models for Personality create/read/update, PersonalitySummary (no messages).
3. **`routers/personalities.py`** — GET/POST/PUT/DELETE `/personalities`, POST `/personalities/{id}/chat` (accepts message, returns stubbed streaming response).
4. **`services/personality_manager.py`** — In-memory config CRUD + persistence to `~/.hermes/personalities-ui/configs/` as YAML files.
5. **`websocket/handler.py`** — WebSocket endpoint at `/ws/{personality_id}`. Accepts text messages, streams back simulated events: `thinking`, `tool_call` (fake), `tool_result`, `response`, `done`. No real Hermes calls yet.
6. **`main.py`** — CORS, lifespan (init DB + seed demo personalities), mount routers, mount WS handler.

### Frontend

1. **API client (`lib/api/client.ts`)** — fetch wrapper, typed responses.
2. **WebSocket client (`lib/api/websocket.ts`)** — connect, reconnect, event emitter.
3. **Store (`lib/stores/personality.ts`)** — list, active, CRUD actions.
4. **Store (`lib/stores/session.ts`)** — per-personality message history, append events.
5. **Sidebar** — personality list, active personality highlight, cursor states.
6. **ChatView** — message list, input box, send button. Renders simulated tool calls as collapsible cards.
7. **MessageBubble** — user vs assistant styling, thinking indicator, rendering tool calls inline.
8. **Personality edit page (`/personalities/[id]`)** — form for name, system prompt, model, provider, avatar emoji.
9. **Personality create page** — inline or modal form, POST to API, redirect to edit.
10. **`routes/+page.svelte`** — redirect to `/personalities` on empty state.

**Stubs for later:** MCP, provider, cron, usage pages show "Coming Soon" placeholder.

**Verification:** Create a personality in the UI, send a message, see the simulated response stream in with fake tool calls. Refresh and history persists.

## Phase 2 — Real Hermes Integration (1-2 days)

Goal: Chat messages actually route through Hermes SDK (or CLI subprocess) instead of simulated responses.

1. **`services/streaming_bridge.py`** — Real implementation:
   - Accept personality config (system prompt, model, provider, MCP tool list)
   - Spawn Hermes agent via subprocess (`hermes --profile <profile> --json-mode`) or via Hermes Python SDK import
   - Parse stdout for structured events (thinking, tool_call, tool_result, response, done)
   - Stream events to WebSocket
   - Timeout handler (kill agent after 60s)
2. **Personality update** — Add `mcp_server_ids`, `provider_override`, `token_budget` fields. Wire to API.
3. **WS handler update** — Use real `StreamingBridge` instead of simulator.
4. **Error handling** — Agent crash, timeout, tool failure → send `error` event to WS, show in UI.
5. **`models/session.py`** — Full session persistence: user messages, assistant responses, tool call sequences.

**Fallback:** If Hermes SDK isn't available at import time, fall back to CLI subprocess with `hermes run` piping through a JSON protocol shim. Log a warning so the user knows the mode.

**Verification:** Create a personality pointing at a real LLM provider, send a message, watch tool calls stream in real time in the UI.

## Phase 3 — Provider Manager (1-2 days)

Goal: Add/manage/remove LLM providers from the UI. No `hermes config set` needed.

1. **`models/provider.py`** — Provider config: name, type (openai/anthropic/openrouter/ollama/vllm/custom), base_url, api_key (encrypted on write, decrypted on use), models list, note.
2. **`services/provider_manager.py`**:
   - CRUD on provider configs stored in `~/.hermes/personalities-ui/providers/` as encrypted JSON files 
   - Fernet encryption of api_key using key in `~/.hermes/personalities-ui/keys/`
   - Model discovery: `GET {base_url}/v1/models` → parse + cache
   - Connection test: try `POST {base_url}/v1/chat/completions` with a minimal message
   - Multi-region/round-robin support (optional pool config)
3. **`routers/providers.py`** — GET/POST/PUT/DELETE `/providers`, POST `/providers/{id}/test`, GET `/providers/{id}/models`
4. **Config.yaml dual-write** (`services/migration.py`) — On every provider create/update/delete, also write to `~/.hermes/config.yaml` under `custom_providers` or equivalent section. Read current config.yaml first, patch, write back (preserving comments with ruamel.yaml).
5. **Frontend Providers page** — List, add form (type dropdown → dynamic fields), edit, delete. Test button with result indicator. Model list display.

**Verification:** Add an OpenRouter provider with your key, test it, see models populate. Personality edit page lets you select this provider. Send a message → real LLM call works.

## Phase 4 — MCP Management (1-2 days)

Goal: Add/manage MCP servers, assign them to personalities. Tool discovery and tool injection.

1. **`models/mcp_server.py`** — Server config: name, command (for stdio transport), args, env, url (for HTTP transport), type (stdio/http), enabled.
2. **`services/mcp_manager.py`**:
   - CRUD on MCP server configs stored in `~/.hermes/personalities-ui/mcp/` as JSON
   - Connection pool: dict of {server_id: McpClientSession}. Start on enable, stop on disable/reload
   - Tool schema caching: `client.list_tools()` → cache with TTL (60s)
   - Health checks: periodic ping, reconnect on failure
   - Config.yaml dual-write: same strategy as Provider Manager
3. **`routers/mcp.py`** — CRUD, POST `/mcp/{id}/test`, POST `/mcp/{id}/reload`, GET `/mcp/{id}/tools`, GET `/mcp/{id}/status`
4. **Personality-to-MCP assignment** — `POST /personalities/{id}/mcp` replaces the list of assigned MCP server IDs
5. **Streaming bridge update** — When building agent context, inject tools from assigned MCP servers using ScopedToolRegistry (filtered view per personality)
6. **Frontend MCP page** — Server list with status indicators (green/red/grey), add/edit form, test button, tool listing per server
7. **Frontend personality edit** — Multi-select for assigned MCP servers

**Verification:** Add a real MCP server (e.g., filesystem or sqlite MCP). Assign to personality. Send a message, see the tool called and result returned in the chat.

## Phase 5 — Token Usage Tracking (1 day)

1. **`models/token_usage.py`** — TokenUsageRecord (personality_id, session_id, provider, model, prompt_tokens, completion_tokens, cost, timestamp). UsageSummary (personality_id, month, total_tokens, total_cost).
2. **`services/token_tracker.py`**:
   - `record_usage()`: called from streaming bridge after LLM response, writes to SQLite
   - `get_usage()`: by personality, session, time range, or global
   - `check_budget()`: compare running total vs personality.budget, return warning if exceeded
3. **`routers/usage.py`** — GET `/usage?personality_id=X&period=month`, GET `/usage/history?days=30`, GET `/usage/models`, POST `/usage/reset`
4. **Streaming bridge hook** — After each LLM response chunk (or after final), record token usage. Send `usage` event to WebSocket.
5. **Frontend**:
   - Token badge on each assistant message (e.g., "2.1k tokens" or "$0.04")
   - Usage page: per-personality table, monthly totals, model breakdown
   - Personality sidebar: running token/cost total vs budget, color-coded progress bar
   - Config editor: token budget fields (monthly_total, monthly_cost)
   - Notification on budget approaching limit (>80%, >95%)

**Verification:** Chat for a bit, see token counts on each message. Usage page shows accurate totals. Budget warning appears when set low.

## Phase 6 — Cron Jobs (1-2 days)

Goal: Schedule and manage recurring agent tasks from the UI. No `hermes cron create` CLI.

1. **`models/cron_job.py`** — JobConfig: name, schedule (cron expression or human string like "every 2h"), personality_id, prompt template, skills (string list), no_agent (bool), script path, enabled, delivery_target, model override, workdir.
2. **`services/cron_scheduler.py`**:
   - CRUD for jobs stored in `~/.hermes/personalities-ui/cron/` as JSON
   - `apscheduler` backend: AsyncIOScheduler running in-process
   - On tick: create Hermes agent session with personality config → run prompt → capture output → deliver
   - Delivery: Writes to session history, optionally sends to delivery target (telegram, discord, etc.)
   - History: record each tick (status code, duration, output digest, error)
   - Dual-write: also write to Hermes cron DB at `~/.hermes/data/cron.db` via direct SQLite insert
   - On startup: load all enabled jobs from JSON, register with apscheduler
3. **`routers/cron.py`** — CRUD, POST `/cron/{id}/test-run`, POST `/{id}/pause` / `/{id}/resume`, GET `/cron/{id}/history`
4. **Frontend Cron Jobs page** — Schedule list with next-run time, on/off toggle, per-job history (execution timeline with green/red ticks)
5. **Frontend Cron editor** — Form with personality selector, prompt input, schedule input (cron expression with human preview), advanced toggle (no_agent, script path, delivery, workdir)

**Verification:** Create a cron job that runs "every 1m" with a simple prompt. Wait 2 minutes, see 2 execution ticks in history with output.

## Phase 7 — Workflow Engine (1-2 days)

Goal: Chain cron jobs into DAG pipelines.

1. **`models/workflow.py`** — WorkflowConfig (name, enabled, personality_id), WorkflowStep (workflow_id, step_order, job_id, depends_on, condition, on_success, on_failure, repeat_until).
2. **`services/workflow_engine.py`**:
   - DAG validation on save (no cycles, all refs exist)
   - Step runner: when upstream job completes, evaluate condition, run next step
   - Condition evaluation: agent-based (`if "stock" in last_output`) or basic (always run)
   - History: per-step record (status, duration, output, error)
3. **`routers/workflows.py`** — CRUD, POST `/workflows/{id}/run`, GET `/workflows/{id}/history`
4. **Frontend Workflows page** — Pipeline view: drag-reorderable step list, visual DAG, per-step condition editor
5. **Workflow history** — Timeline view showing each step's result

**Verification:** Create 2 cron jobs, chain them in a workflow (job1 → job2), trigger the workflow, see both run in sequence.

## Phase 8 — Initial Config Migration + First-Boot Experience (1-2 days)

Goal: First time the UI starts, it discovers existing Hermes config and offers to import.

1. **`services/migration.py`** — Full implementation:
   - `scan_existing_config()`: read config.yaml, profile dirs, cron DB, MCP config
   - `build_inventory()`: return all discoverable resources grouped by category
   - `adopt_providers()`: read `config.yaml` → extract `custom_providers` + `default_provider` → create provider configs
   - `adopt_mcp_servers()`: read `config.yaml` → extract `mcp_servers` → create MCP configs
   - `adopt_profiles()`: scan `~/.hermes/profiles/` → create personality configs (name, system prompt from profile's config)
   - `write_yaml()`: ruamel.yaml writer that inserts/updates/deletes keys while preserving comments
   - `sync_status()`: compare in-memory config vs current config.yaml, report drift
2. **Frontend first-boot wizard**:
   - Screen 1: "Found X providers, Y MCP servers, Z profiles." Show inventory.
   - Screen 2: Checkboxes for what to import. "Import providers?" (default: yes). "Import MCP?" (default: yes). "Create personalities from profiles?" (default: yes).
   - Screen 3: Migration summary — "Imported 3 providers, 2 MCP servers, 4 personalities."
   - Screen 4: "Start chatting" button.
   - Re-triggerable from Settings page ("Re-scan Hermes config").
3. **Per-personality YAML export** — Button on personality edit page: "Export as Hermes profile" → creates `~/.hermes/profiles/.ui-export/<personality-id>/` with proper YAML config files and a profile manifest.

**Verification:** Start the UI with an existing Hermes install. See the inventory screen. Import everything. Chat with an imported personality using its original provider. Run `hermes --profile .ui-export/my-personality` and confirm it works.

## Phase 9 — Production Polish (ongoing)

- Authentication (API key or OAuth for multi-user)
- SSL/HTTPS
- Docker Compose healthchecks + restart policies
- Logging (structured JSON logs)
- Error reporting (sent to session output, visible in UI)
- Rate limiting
- Backup/restore for config JSON files
- Pagination for large result sets (history, usage)
- UI loading states, error boundaries, empty states

## Integration Testing

After each phase, test three scenarios:

1. **Fresh install** — No existing Hermes config. Create everything from UI. Verify data persists across restart.
2. **Existing install** — Has profiles, providers, cron jobs. Run migration. Verify nothing lost.
3. **CLI coexistence** — After UI creates/modifies configs, verify `hermes config list`, `hermes cron list`, `hermes --profile x` still work. After CLI modifies configs, verify UI picks up changes on next load.

## If You Get Stuck

Stick to the contract: any placeholder or stub is fine as long as the API surface and data structures match. The architecture doc in `Reference/` has the full detail on each component — read it for design intent. When in doubt, stub it with a `raise NotImplementedError` and a log line, then move to the next phase.
