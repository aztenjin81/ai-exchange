---
type: reference
status: draft
date: 2026-06-13
tags: [hermes, web-ui, architecture, personalities, mcp, token-tracking, llm-management]
---

# Hermes Personalities UI — Architecture

A web UI like Open WebUI, but instead of switching models, it switches entire Hermes agent personalities — each with its own model, provider, system prompt, skills, toolset, MCP servers, memory, and token budget.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     SvelteKit SPA                           │
│  ┌──────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ │
│  │Side- │ │  Chat    │ │ Config   │ │  MCP   │ │Provider│ │
│  │ bar  │ │  View    │ │ Editor   │ │Manager │ │Manager │ │
│  └──┬───┘ └────┬─────┘ └────┬─────┘ └───┬────┘ └───┬────┘ │
│     └──────────┴────────────┴────────────┴──────────┘      │
│                        │ WebSocket                          │
└────────────────────────┼────────────────────────────────────┘
                         │
┌────────────────────────┼────────────────────────────────────┐
│              FastAPI Server (Python)                        │
│  ┌──────────┐  ┌───────────────────┐  ┌───────────────────┐ │
│  │REST + WS │◄─┤ Streaming Bridge  │◄─┤ Personality Mgr   │ │
│  └──────────┘  └────────┬──────────┘  └───────────────────┘ │
│                         │                                    │
│  ┌────────────────┐ ┌───┴────────┐ ┌────────────────────┐   │
│  │  Token Tracker  │ │Hermes SDK  │ │  MCP Server Mgr   │   │
│  └────────────────┘ │(AgentLoop) │ └────────────────────┘   │
│                     └─────┬──────┘                          │
│  ┌────────────────────┐   │         ┌──────────────────────┐│
│  │ LLM Provider Mgr   │   │         │  SQLite + JSON Store ││
│  └────────────────────┘   │         └──────────────────────┘│
│                           │                                  │
└───────────────────────────┼──────────────────────────────────┘
                            │
                    ┌───────┴───────┐
                    │  config.yaml  │
                    │  + .env       │
                    │  + profiles/  │
                    └───────────────┘
```

## Backend Components

### 1. FastAPI Server

REST + WebSocket server with personality-scoped routing.

**REST Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/personalities` | List all personalities |
| `POST` | `/personalities` | Create new personality |
| `GET` | `/personalities/{id}` | Get personality detail |
| `PUT` | `/personalities/{id}` | Update personality |
| `DELETE` | `/personalities/{id}` | Delete personality |
| `POST` | `/personalities/{id}/duplicate` | Clone from existing |
| `POST` | `/personalities/{id}/test` | Test connection (ping model) |
| `GET` | `/personalities/{id}/sessions` | Session history for this personality |
| `DELETE` | `/personalities/{id}/sessions/{sid}` | Delete a session |
| `GET` | `/personalities/{id}/usage` | Token usage for this personality |
| `GET` | `/personalities/{id}/usage/history` | Time-series usage data |
| `POST` | `/personalities/{id}/usage/reset` | Reset usage period counter |
| `GET` | `/usage/global` | Aggregate usage across all personalities |
| `GET` | `/usage/models` | Per-model breakdown |
| `GET` | `/mcp/servers` | List all MCP servers |
| `POST` | `/mcp/servers` | Add an MCP server config |
| `PUT` | `/mcp/servers/{id}` | Update MCP server config |
| `DELETE` | `/mcp/servers/{id}` | Remove MCP server |
| `POST` | `/mcp/servers/{id}/test` | Test MCP connection |
| `POST` | `/mcp/servers/{id}/reload` | Hot-reload MCP tools |
| `GET` | `/mcp/servers/{id}/tools` | List discovered tools |
| `GET` | `/providers` | List configured providers |
| `POST` | `/providers` | Add provider config |
| `PUT` | `/providers/{id}` | Update provider config |
| `DELETE` | `/providers/{id}` | Remove provider config |
| `POST` | `/providers/{id}/test` | Test provider connection + list models |
| `GET` | `/providers/{id}/models` | List available models from this provider |
| `GET` | `/providers/models/browse` | Browse model catalog across all providers |
| `PUT` | `/providers/credentials` | Bulk update credential pools |
| `GET` | `/providers/auxiliary` | List auxiliary task provider assignments |
| `PUT` | `/providers/auxiliary` | Update auxiliary task provider mappings |
| `GET` | `/status` | Server health + personality states |
| `GET` | `/config/export` | Export all config as YAML/JSON |

**WebSocket Endpoint:**

```
WS /ws?personality_id={id}&session_id={sid}
```

Bidirectional communication per personality session. Client sends messages, server streams events back (see Streaming Bridge for event types).

### 2. Personality Manager

The core orchestrator. Maps each personality to its runtime configuration.

**Personality Config Model:**

```yaml
personality:
  id: "researcher"
  name: "Research Analyst"
  avatar: "🔬"
  color: "#4A90D9"
  enabled: true

  # --- LLM Config ---
  provider: "openrouter"
  model: "openai/gpt-4o"
  base_url: ""
  api_key: ""              # empty = use profile default from .env
  api_mode: "chat_completions"
  temperature: 0.3
  max_tokens: 4096
  reasoning_effort: "high"

  # --- Fallback ---
  fallback_providers:
    - provider: "anthropic"
      model: "claude-sonnet-4"

  # --- System & Skills ---
  system_prompt: "You are a thorough research assistant..."
  skills:
    enabled: ["web-search", "arxiv", "data-analysis"]
    disabled: ["cron", "homeassistant"]

  # --- Toolsets ---
  toolsets:
    enabled: ["web", "file", "terminal", "skills"]
    disabled: ["browser", "image_gen", "homeassistant"]
  tools: {}                # per-tool toggles (fine-grained)

  # --- MCP ---
  mcp_servers:
    - "postgres-db"
    - "web-scraper"

  # --- Session ---
  session_ttl_hours: 168   # auto-archive after 7 days
  max_history_turns: 200   # trim to this before context compression

  # --- Token Budget ---
  token_budget:
    monthly_total: 100000000  # 100M tokens
    monthly_cost_usd: 50.00   # hard cap in dollars
    notify_at_pct: 80         # alert at 80%

  # --- Memory ---
  memory_provider: "hindsight"
  memory_enabled: true
  user_profile_enabled: true
```

**Session Routing:**

1. Client opens WebSocket with `personality_id`
2. Personality Manager resolves the personality config (DB → full spec)
3. Creates an isolated Hermes agent instance:
   - Builds `config.yaml` merge from base profile + personality overrides
   - Loads skills, toolsets, MCP connections
   - Sets system prompt, temperature, etc.
   - Attaches Token Tracker hooks
4. Agent runs until session closes; agent state is garbage-collected
5. Session history persisted to SQLite

**Personality Inheritance Model:**

Personalities can inherit from a base profile, layering overrides:

```
Base Profile (researcher_base)
  provider: openrouter
  model: openai/gpt-4o
  skills: [web-search, arxiv]
  mcp: [postgres-db]
    │
    ├── Personality A (deep-researcher)
    │     model: openai/o3
    │     skills: +[data-analysis]
    │
    └── Personality B (lit-reviewer)
          model: anthropic/claude-sonnet-4
          skills: +[zotero]
```

### 3. Streaming Bridge

The critical path. Hermes' agent loop is turn-based — it runs a full cycle (LLM call → tool calls → more LLM calls → final response) before returning. The bridge converts this into real-time event stream.

**Architecture:** Patch Hermes' `AIAgent` to emit lifecycle events via a callback/publisher interface rather than printing to stdout.

**Event Schema (server → client, JSON over WebSocket):**

```json
// New turn started (user message received)
{"type": "turn_start", "turn": 1, "message": "Analyze this dataset"}

// Model starts thinking
{"type": "thinking", "content": "Let me look at the CSV file first..."}

// Model emits partial text (streaming)
{"type": "token", "content": "Looking at the data,"}

// Tool call initiated
{"type": "tool_call", "name": "read_file", "args": {"path": "data.csv"}, "id": "call_abc123"}

// Tool result returned
{"type": "tool_result", "name": "read_file", "id": "call_abc123", "truncated": false}

// Token usage snapshot (after each LLM call)
{"type": "usage", "prompt_tokens": 1250, "completion_tokens": 340, "total_tokens": 1590,
 "cost_usd": 0.0477, "model": "openai/gpt-4o", "provider": "openrouter",
 "personality_id": "researcher", "session_id": "sess_001"}

// Budget exceeded (pre-flight check failed)
{"type": "budget_exceeded", "budget_type": "monthly_cost", "limit": 50.00,
 "current": 48.20, "estimated_cost": 2.50}

// Final response for this turn
{"type": "response", "content": "Looking at the data, I found..."}

// Session-level event
{"type": "status", "state": "compressing|idle|error", "detail": "..."}

// Turn complete (agent loop iteration finished)
{"type": "turn_end", "turn": 1, "usage_summary": {...}}

// Error
{"type": "error", "code": "PROVIDER_ERROR", "message": "OpenRouter 429 rate limited"}
```

**Implementation approaches (in order of preference):**

1. **SDK Mode (preferred):** Import Hermes `run_agent.py` classes directly. Add an event emitter interface (`AgentEventHandler`) that the agent loop calls at each lifecycle point. The bridge subscribes and forwards to WebSocket clients.

2. **Subprocess Bridge (fallback):** Spawn `hermes chat -q` with `--verbose` flags and parse stdout for tool call markers, thinking blocks, etc. Fragile — requires maintaining a parser for Hermes' output format.

3. **Hermes Gateway API Adapter:** Route through Hermes' existing API server if it exposes enough hooks. Currently limited.

### 4. MCP Server Manager

Owns MCP server configurations and connection lifecycle independently from Hermes' global `config.yaml`.

**Server Config Model:**

```yaml
mcp_server:
  id: "postgres-db"
  name: "PostgreSQL Analytics"
  type: "stdio"             # "stdio" or "url"
  command: "npx"
  args: ["@anthropic/mcp-postgres", "postgresql://..."]
  env:
    PGPASSWORD: ""          # stored encrypted, resolved at runtime
  enabled: true
  auto_connect: true
  health_check_interval: 60
  personality_ids:          # assigned personalities (reference counted)
    - "researcher"
    - "analyst"
    - "data-pipeline"
```

**Connection Pool:**

- Shared connections with reference counting. If 3 personalities use `postgres-db`, only 1 process runs.
- On last personality disconnect → graceful shutdown
- On first personality connect → spawn process
- Health monitor pings every N seconds, reconnects with exponential backoff (2s, 4s, 8s, ... 60s max)

**Personality-to-MCP Assignment:**

- Each personality has a `mcp_servers` list in its config
- At agent creation time, MCP Server Manager injects the assigned servers' tools into the personality's tool schema
- Tool names are prefixed with the server name to avoid collisions (e.g., `postgres_query`, `scraper_fetch`)

**Tool Schema Caching:**

MCP `listTools()` response can be large. The manager caches the schema per server and only re-fetches on explicit reload or reconnect. This keeps personality startup fast.

### 5. Token Tracker

Captures per-call token usage from every LLM interaction in the agent loop.

**What Gets Tracked:**

| Field | Source | Example |
|-------|--------|---------|
| `personality_id` | Session context | `"researcher"` |
| `session_id` | Session context | `"sess_abc123"` |
| `turn_number` | Agent loop counter | `3` |
| `model` | LLM response metadata | `"openai/gpt-4o"` |
| `provider` | LLM response metadata | `"openrouter"` |
| `prompt_tokens` | LLM response.usage | `1250` |
| `completion_tokens` | LLM response.usage | `340` |
| `cached_prompt_tokens` | LLM response (if available) | `800` |
| `cost_usd` | Calculated from pricing table | `0.0477` |
| `timestamp` | Server clock | `2026-06-13T14:30:00Z` |

**Pricing Table:**

Built-in mapping covering common models. Extensible via config:

```yaml
# Built-in defaults (overridable per personality)
pricing:
  openai/gpt-4o:
    prompt: 0.0000025       # per token
    completion: 0.00001
  openrouter/anthropic/claude-sonnet-4:
    prompt: 0.000003
    completion: 0.000015
  _default:
    prompt: 0.000001        # fallback for unknown models
    completion: 0.000004
```

**Capture Point:**

The Token Tracker hooks into the Streaming Bridge's event emitter. After each LLM completion event (before tool dispatch or final response emission), it:

1. Extracts `usage` metadata from the provider response
2. Looks up model pricing from the pricing table (or falls back to `_default`)
3. Computes `cost_usd = prompt_tokens * prompt_rate + completion_tokens * completion_rate`
4. Writes the row to `token_usage` table
5. Updates in-memory summary for the current personality
6. Triggers budget check — if exceeded, emits `budget_exceeded` event

**Budget Enforcement:**

Checked at the start of each agent turn (before LLM call):

- `monthly_total` — if personality.token_budget.monthly_total is set and exceeded, the turn is blocked and `budget_exceeded` is returned
- `monthly_cost` — if personality.token_budget.monthly_cost is set and exceeded, same block
- Budget period rolls monthly (calendar month)
- Budgets are checked against the *running total including* the cost of the prompt about to be sent (estimated from compressed context size)

**Cost Recalculation:**

Raw token counts are always preserved. If pricing changes, all historical costs can be recalculated. The cost field is a derived convenience value.

### 6. LLM Provider Manager

Manages LLM provider configurations independently from Hermes' `config.yaml`, enabling the UI to add/remove/edit providers, manage credentials, and assign models to personalities — all without touching the CLI.

**Provider Config Model:**

```yaml
provider:
  id: "my-openrouter"
  name: "My OpenRouter Account"
  type: "openrouter"                 # provider type key
  display_name: "OpenRouter (Pro)"
  enabled: true

  # --- Connection ---
  base_url: "https://openrouter.ai/api/v1"
  api_mode: "chat_completions"       # chat_completions | completions | etc.

  # --- Credentials ---
  credentials:
    primary:
      key: "sk-or-v1-..."           # stored encrypted at rest
      key_env_var: "OPENROUTER_API_KEY"  # or reference env var instead
    pool:                            # credential pool for rotation
      - key_env_var: "OPENROUTER_KEY_2"
      - key_env_var: "OPENROUTER_KEY_3"
    strategy: "round-robin"          # round-robin | lowest-usage | random

  # --- Model Discovery ---
  models: []                         # populated by test/discovery on add
  model_discovery_url: ""            # optional custom model list endpoint
  auto_discover: true                # fetch model list on connect

  # --- Limits ---
  rate_limit_rpm: 10000
  rate_limit_tpm: 10000000
  max_context_length: 128000
  supports_streaming: true
  supports_function_calling: true

  # --- Metadata ---
  notes: "Primary provider for production personalities"
  tags: ["production", "primary"]
```

**Supported Provider Types:**

The full 20+ from Hermes' provider list. Each type has a templated default config (base URL, API mode, supported features):

| Type Key | Default Base URL | Notes |
|----------|-----------------|-------|
| `openrouter` | `https://openrouter.ai/api/v1` | |
| `anthropic` | `https://api.anthropic.com` | |
| `opencode-go` | `https://opencode.ai/zen/go/v1` | |
| `opencode-zen` | `https://opencode.ai/zen/v1` | |
| `openai` | `https://api.openai.com/v1` | |
| `google-gemini` | `https://generativelanguage.googleapis.com/v1beta` | |
| `deepseek` | `https://api.deepseek.com` | |
| `xai` | `https://api.x.ai` | |
| `github-copilot` | (OAuth flow) | Special auth flow |
| `huggingface` | `https://api-inference.huggingface.co` | |
| `custom` | (user-defined) | OpenAI-compatible endpoint template |

**Credential Storage:**

- API keys stored encrypted at rest (AES-256-GCM with a server-side master key, or OS keychain integration)
- UI never displays full keys — shows masked preview (`sk-or-v1-...a3b8`)
- Keys can reference env vars (for container deployments where secrets come from environment)
- Credential pools for rate-limit spreading across multiple keys

**Model Discovery Flow:**

1. User adds/edits a provider
2. Clicks "Test & Discover" button
3. Backend calls `GET /v1/models` (or provider-specific equivalent)
4. Returns list of available models with metadata (context length, pricing, capabilities)
5. Models are cached in the `provider_models` table, refreshed on demand
6. User browses and assigns models to personalities

**Auxiliary Task Provider Mapping:**

In Hermes' config, each auxiliary task (vision, compression, approval, etc.) can have its own provider override. The Provider Manager exposes this as a grid:

```
Auxiliary Task    | Provider            | Model
──────────────────|─────────────────────|────────────────────
Vision            | openrouter          | openai/gpt-4o
Compression       | anthropic           | claude-sonnet-4
Approval          | opencode-go         | deepseek-v4-flash
MCP               | <inherit>           | <inherit>
Web Extract       | openrouter          | openai/gpt-4o-mini
```

Each cell is editable. Changes sync to the personality's effective config.

**Provider Assignment Flow:**

```
Provider Manager DB
    │
    ├── personality.researcher ──── provider: openrouter, model: gpt-4o
    ├── personality.analyst ─────── provider: anthropic,  model: claude-sonnet-4
    └── personality.coder ───────── provider: custom:litellm, model: llama-3-70b

    │
    ▼
Personality Manager builds config.yaml merge:
  personality config → overrides base profile → merges provider details → resolved config
```

## Data Flow (End-to-End Turn)

```
1. User types message in Chat View
2. SvelteKit sends via WebSocket: {"type":"message","content":"Analyze this CSV"}
3. Streaming Bridge receives → creates agent turn
4. Personality Manager resolves personality config (pull provider, model, MCP, skills)
5. MCP Server Manager: ensure personality's assigned servers are connected
6. Token Tracker: pre-flight budget check (ok → proceed, fail → budget_exceeded event)
7. Agent loop runs:
   a. Build prompt with system prompt + skills + MCP tools + session history
   b. Call LLM via Personality Manager (using resolved provider/model)
   c. Token Tracker: record usage after LLM response
   d. Streaming Bridge: emit thinking/token/tool_call/tool_result events as they happen
   e. Repeat until final response
8. Token Tracker: update personality's running totals and session summary
9. Streaming Bridge: emit response + turn_end with usage summary
10. Frontend renders: text response, tool call badges, token usage display
11. Session history persisted to SQLite
```

## Frontend Components

### Personality Sidebar

Left sidebar listing all personalities. Each entry shows:
- Avatar emoji + name
- Active indicator (green dot if connected + agent idle)
- Provider/model badge (small text, e.g. "GPT-4o")
- Token usage for current period (running total, color-coded if approaching budget)
- Quick actions: pin to top, start new session, delete

### Chat View

Main chat area for the selected personality:
- Message bubbles with standard chat layout (user left, assistant right)
- Each assistant response shows a token badge in the footer (e.g. "1,590 tok | $0.048")
- Tool call rendering: collapsible cards showing tool name, args, result (with truncation indicator)
- Thinking blocks: expandable if `reasoning_effort` emits them
- Multi-turn within same view (scrollback)
- Session search within the current personality's history

### Personality Config Editor

Modal or full-page editor for creating/editing a personality:
- Name, avatar, color, enabled toggle
- Provider selector (from LLM Provider Manager's list of configured providers)
- Model selector (populated from provider's discovered models, with search)
- Temperature, max_tokens, reasoning_effort sliders
- Base URL override (for custom endpoints)
- API key field (masked, with "use env var" option)
- System prompt textarea (with template variables `{{date}}`, `{{timezone}}`, etc.)
- Skills: enabled/disabled toggles with search+filter
- Toolsets: enabled/disabled toggles
- MCP servers: multi-select from MCP Server Manager's list
- Fallback providers: ordered list with add/remove
- Token budget: monthly token cap + monthly cost cap + notification threshold
- Test button: pings the model to verify the config works
- Duplicate button: clone an existing personality

### MCP Management View

Dedicated page for managing MCP servers:
- Server list with status indicators (connected, disconnected, error, reconnecting)
- Add form: name, type (stdio/url), command/URL, args, environment variables (masked)
- Server detail view: discovered tools list with schemas, current connection log
- Test button: connects to server, runs `listTools()`, shows results
- Reload button: re-runs `listTools()` to refresh schema cache
- Personality assignments: inline list of which personalities use this server
- Health monitor log: last N pings with timing

### LLM Provider Manager View

Dedicated page for managing providers:
- Provider list with status (configured, connected, error), last tested timestamp
- Add form: provider type selector (dropdown of 20+ supported types), display name, base URL, API mode
- Credential management: primary key input (masked), credential pool manager (add/remove pool keys), strategy selector
- Test & Discover: initiates connection, fetches model list, returns discovered models with pricing
- Model browser: full list of discovered models with search/filter by context length, pricing, capabilities
- Per-personality assignment grid: quick-view of which personalities use which provider/model
- Auxiliary task mapping: grid of auxiliary tasks → provider assignments
- Export view: see the effective config.yaml that will be generated

### Token Usage Dashboard

Tab in the personality view or a global page:
- Current period summary: tokens used, cost, budget remaining
- Time-series chart: tokens/cost over days (last 7, 30, this month)
- Per-model breakdown: which models consumed what share
- Per-session breakdown: top sessions by token usage
- Budget progress bars: visual indicator of how close each personality is to its cap
- Export: download usage data as CSV/JSON

## State & Persistence

| Data | Storage | Notes |
|------|---------|-------|
| Personality configs | `personalities/` JSON files + SQLite | JSON for human-editable, SQLite for fast queries |
| MCP server configs | `mcp/` JSON files + SQLite | Same dual approach |
| Provider configs | `providers/` JSON (encrypted keys) + SQLite | Keys encrypted at rest |
| Provider model cache | SQLite (`provider_models`) | Auto-refresh on test, manual refresh |
| Auxiliary task mapping | SQLite (`auxiliary_providers`) | |
| Session history | SQLite (`sessions`, `messages`) | Hermes-compatible format |
| Token usage | SQLite (`token_usage`) | Append-only, periodic archival |
| Personality usage summary | SQLite (`personality_usage_summary`) | Materialized per-period totals |
| User preferences | SQLite (`preferences`) | Theme, layout, defaults |
| Runtime agent states | In-memory dict | Not persisted — ephemeral agent instances |

**SQLite Schema (extensions beyond Hermes' default):**

```sql
-- Personality configs (mirrored from JSON for fast queries)
CREATE TABLE personalities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    avatar TEXT,
    color TEXT,
    enabled INTEGER DEFAULT 1,
    provider TEXT,
    model TEXT,
    base_url TEXT,
    api_mode TEXT DEFAULT 'chat_completions',
    temperature REAL DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 4096,
    reasoning_effort TEXT DEFAULT 'medium',
    system_prompt TEXT,
    fallback_providers TEXT,    -- JSON array
    skills_enabled TEXT,        -- JSON array
    skills_disabled TEXT,       -- JSON array
    toolsets_enabled TEXT,      -- JSON array
    toolsets_disabled TEXT,     -- JSON array
    token_budget_monthly_total INTEGER,
    token_budget_monthly_cost REAL,
    token_budget_notify_pct REAL,
    session_ttl_hours INTEGER DEFAULT 168,
    max_history_turns INTEGER DEFAULT 200,
    memory_provider TEXT,
    memory_enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- MCP server configs
CREATE TABLE mcp_servers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    server_type TEXT NOT NULL,   -- 'stdio' | 'url'
    command TEXT,
    args TEXT,                   -- JSON array
    env TEXT,                    -- JSON object (keys masked)
    enabled INTEGER DEFAULT 1,
    auto_connect INTEGER DEFAULT 1,
    health_check_interval INTEGER DEFAULT 60,
    last_connected_at TIMESTAMP,
    last_error TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Personality-to-MCP assignment
CREATE TABLE personality_mcp (
    personality_id TEXT NOT NULL,
    mcp_server_id TEXT NOT NULL,
    PRIMARY KEY (personality_id, mcp_server_id),
    FOREIGN KEY (personality_id) REFERENCES personalities(id),
    FOREIGN KEY (mcp_server_id) REFERENCES mcp_servers(id)
);

-- MCP tool schema cache
CREATE TABLE mcp_tool_cache (
    server_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    tool_schema TEXT NOT NULL,   -- JSON schema
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (server_id, tool_name),
    FOREIGN KEY (server_id) REFERENCES mcp_servers(id)
);

-- LLM provider configs
CREATE TABLE providers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider_type TEXT NOT NULL,  -- 'openrouter', 'anthropic', 'custom', etc.
    display_name TEXT,
    base_url TEXT,
    api_mode TEXT DEFAULT 'chat_completions',
    enabled INTEGER DEFAULT 1,
    key_encrypted TEXT,           -- encrypted primary key
    key_env_var TEXT,             -- or env var reference
    pool_config TEXT,             -- JSON: credential pool config
    rate_limit_rpm INTEGER,
    rate_limit_tpm INTEGER,
    max_context_length INTEGER,
    supports_streaming INTEGER DEFAULT 1,
    supports_fn_calling INTEGER DEFAULT 1,
    auto_discover INTEGER DEFAULT 1,
    notes TEXT,
    tags TEXT,                    -- JSON array
    last_tested_at TIMESTAMP,
    last_error TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Provider model cache
CREATE TABLE provider_models (
    provider_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    display_name TEXT,
    context_length INTEGER,
    max_output_tokens INTEGER,
    pricing_prompt_per_token REAL,
    pricing_completion_per_token REAL,
    supports_streaming INTEGER DEFAULT 1,
    supports_fn_calling INTEGER DEFAULT 1,
    supports_vision INTEGER DEFAULT 0,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (provider_id, model_id),
    FOREIGN KEY (provider_id) REFERENCES providers(id)
);

-- Auxiliary task provider mapping
CREATE TABLE auxiliary_providers (
    personality_id TEXT NOT NULL,
    task_name TEXT NOT NULL,       -- 'vision', 'compression', 'approval', etc.
    provider_id TEXT,              -- NULL = inherit personality's provider
    model_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (personality_id, task_name),
    FOREIGN KEY (personality_id) REFERENCES personalities(id),
    FOREIGN KEY (provider_id) REFERENCES providers(id)
);

-- Token usage rows (append-only)
CREATE TABLE token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    personality_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    turn_number INTEGER,
    model TEXT NOT NULL,
    provider TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cached_prompt_tokens INTEGER,
    total_tokens INTEGER,
    cost_usd REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (personality_id) REFERENCES personalities(id)
);

-- Materialized usage summaries per personality per period
CREATE TABLE personality_usage_summary (
    personality_id TEXT NOT NULL,
    period_start DATE NOT NULL,       -- first day of month
    total_prompt_tokens INTEGER DEFAULT 0,
    total_completion_tokens INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (personality_id, period_start),
    FOREIGN KEY (personality_id) REFERENCES personalities(id)
);

-- Session history (Hermes-compatible)
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    personality_id TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    FOREIGN KEY (personality_id) REFERENCES personalities(id)
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,          -- 'user', 'assistant', 'tool'
    content TEXT,
    tool_calls TEXT,             -- JSON
    tool_call_id TEXT,
    token_usage_id INTEGER,      -- link to token_usage for assistant messages
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

## Hard Parts

### 1. Streaming Bridge — Hermes Doesn't Stream

Hermes' agent loop is fundamentally turn-based. The LLM may stream tokens, but the agent loop collects the full response before dispatching tools. To get real-time events, we need to either:

A) **Patch Hermes core** — Add an `AgentEventHandler` interface to `run_agent.py` that fires at each lifecycle point. This is the cleanest approach but requires maintaining a fork or contributing upstream.

B) **Subprocess bridge** — Run `hermes` as a subprocess with `--verbose`, capture its TUI output. Fragile, but zero code changes to Hermes.

C) **Gateway API mode** — Use Hermes' existing WebSocket API server if it exposes sufficient hooks. Current API server is designed for chat, not agent-loop introspection.

**Recommendation:** Approach A (SDK mode with event hooks). Start with a thin wrapper that plugs into `run_conversation()`, contributing changes upstream if the Hermes team accepts them.

### 2. Session Isolation — N × Context Window Cost

Each personality is a full Hermes agent with its own context window. Running 5 personalities simultaneously = 5× the memory of a single agent.

| Personality count | Estimated RAM (128K context) | Notes |
|------------------|------------------------------|-------|
| 1 | ~2-4 GB | Single agent |
| 5 | ~10-20 GB | Typical multi-personality |
| 10 | ~20-40 GB | Heavy usage |
| 20 | ~40-80 GB | Power user / team |

**Mitigations:**
- Unload idle personalities after TTL (session_ttl_hours)
- Context compression to reduce window size
- Only keep active personalities fully loaded; swap inactive ones to disk
- Rate-limit max concurrent active personalities per user

### 3. MCP Hot-Reload Gap

Hermes' MCP implementation doesn't support adding or removing servers at runtime without restarting the gateway. The Personality Manager needs per-session MCP injection, which means:

- MCP connections must be managed at the application layer (MCP Server Manager), not delegated to Hermes' config.yaml
- On personality startup, the MCP Server Manager connects the required servers and injects the tools into the agent's tool schema
- On personality teardown, the reference count decrements and the server process cleans up only when the last consumer disconnects
- This bypasses Hermes' native MCP lifecycle entirely — the Personality UI manages its own MCP processes

### 4. Tool Output UX

Hermes tools can return large outputs (file reads, web extracts, terminal output). The chat UI needs to handle:

- Collapsible tool call cards (show args, toggle result visibility)
- Truncation indicators (original size vs displayed preview)
- Streaming tool results (if the tool takes time)
- Error state rendering (red badge with error message)
- Tool call timing (how long each call took)

### 5. MCP Process Management and Security

| Challenge | Description | Mitigation |
|-----------|-------------|------------|
| Zombie processes | MCP server processes that don't clean up on crash | Process group monitoring, SIGTERM → SIGKILL timeout, periodic orphan sweep |
| Stale connections | Connection pool holding dead processes | Heartbeat with configurable interval, stale detection |
| Encrypted env vars | Server configs may contain DB passwords, API keys in `env` field | AES-256-GCM encryption at rest, decrypted in-memory at process spawn time, never logged |
| Tool injection timing | MCP tools must be available before the agent's first tool round | Connect MCP servers during personality initialization (blocking), timeout after N seconds with partial toolset |
| Scoped vs global registries | Tools from different MCP servers need namespace isolation | Tool name prefixing (`server_name.tool_name`), per-personality filtered tool schema |
| Schema bloat | 10 MCP servers with large schemas = massive prompt overhead | Schema caching + optional tool pruning per personality (only inject commonly-used tools, cache the rest) |
| Concurrent schema fetch | Multiple personalities starting simultaneously hitting the same MCP server | Lock per server ID; first request does discovery, subsequent requests wait and use cached result |

### 6. Token Tracking Challenges

| Challenge | Description | Mitigation |
|-----------|-------------|------------|
| Multi-turn costs | A single user message can trigger 2-5 LLM calls (reasoning + tool calls + final response) | Track per-LLM-call, aggregate per-turn in the bridge |
| Provider inconsistency | Some providers report `usage` differently. OpenRouter includes a `usage` object, Anthropic uses a different shape, local models may not report at all | Defensive parsing with per-provider extractors; fallback to estimated tokens when usage not reported |
| Pricing changes | Model pricing changes over time (OpenAI cuts prices, Anthropic adjusts) | Raw token counts always preserved; cost is recalculated on read if pricing table updated |
| Budget race conditions | Two concurrent sessions for the same personality could both pass the budget check | Mutex per personality on budget check + atomic increment on the usage summary |
| Cached tokens | Prompt caching reduces cost but providers report it differently | Track `cached_prompt_tokens` separately if available; apply discounted rate |
| Streaming token counting | During streaming, tokens are incremental — accurate count only available at end | Display running estimate during streaming, finalize after LLM response completes |

### 7. LLM Provider Management Challenges

| Challenge | Description | Mitigation |
|-----------|-------------|------------|
| Key security | API keys must never be stored in plaintext, never appear in logs, never sent to frontend | AES-256-GCM encryption at rest; masked preview only in UI; separate key management endpoint |
| Key rotation | Credential pools need key rotation without downtime | Pool strategy supports "drain" mode (stop using old key for new requests but allow in-flight completion) |
| Provider diversity | Each provider has different auth, base URL, API format, rate limits | Template system per provider type; provider-specific adapter classes for edge cases (OAuth flows, etc.) |
| Model discovery API variance | `GET /v1/models` response format differs per provider | Per-provider response parser with fallback (return raw JSON for custom endpoints) |
| Credential exhaustion detection | Rate limits, billing holds, key revocation | Track HTTP 429/401/403 per key; mark exhausted keys; auto-failover to pool |
| Stale model cache | Model lists change (new models added, old ones deprecated) | Auto-refresh on provider test; periodic background refresh; "refresh models" button |
| Auxiliary provider split brain | Vision provider differs from main provider; each agent call needs two separate LLM round-trips | Personality Manager resolves each auxiliary task independently and emits separate usage events |

### 8. Streaming Bridge Token Sequencing

During a single agent turn, the sequence of events is:

```
User message
  → LLM call #1 (reasoning/planning) → usage event #1
    → Tool call → Tool result
      → LLM call #2 (analysis with tool data) → usage event #2
        → Tool call → Tool result
          → LLM call #3 (final response) → usage event #3
            → turn_end with aggregated usage
```

|Each usage event is emitted immediately so the frontend can update the running token counter. The `turn_end` event carries an aggregate summary. A single user message can produce 2-5 LLM calls depending on how many tools are needed.

## Open Questions

1. **Inheritance model complexity** — How deep should personality inheritance go? Base profile → child → grandchild? Or flat inheritance with overrides only?

2. **File uploads** — How does Open WebUI's file upload (images, PDFs, code files) map to Hermes' tool calls? File context injection vs knowledge base?

3. **Concurrent personality execution** — Should the user be able to send messages to multiple personalities simultaneously (like ChatGPT tabs) or only one at a time?

4. **MCP credential storage** — MCP server env vars may contain database passwords, API keys, tokens. Same encryption strategy as LLM provider keys? Separate encryption domain?

5. **MCP server sharing model** — Can two users share an MCP connection? (Multi-tenant concern.) Or is each user's connection pool fully isolated?

6. **MCP marketplace** — Should the UI include a MCP server browser/discovery (like Open WebUI's model browser but for MCP tools)? Download community MCP server configs?

7. **Per-session vs per-personality MCP isolation** — If two sessions of the same personality run simultaneously, do they share the same MCP connection or get separate ones? Shared is more efficient but two sessions could interfere (tool call from session A reads session B's state in a stateful MCP server).

8. **Credential storage at scale** — OS keychain per user vs server-side master key vs HashiCorp Vault? For the MVP, server-side AES-256-GCM with a configurable master key is sufficient.

9. **How to handle providers with OAuth-only auth** (GitHub Copilot, Nous Portal, Qwen) — These can't be configured via static API keys. Do they get special UI treatment (OAuth initiation flow) or skipped for MVP?

10. **Token granularity** — Track per-session, per-turn, per-LLM-call, or all three? Per-LLM-call gives the most granular data but also the most write traffic. Recommendation: per-LLM-call for accuracy, roll up to per-turn/per-session on read.

11. **Local model token counting** — Ollama/vLLM/local models may not report token usage at all. Fallback: estimate from character count × model-specific ratio, or count with a local tokenizer.

12. **Streaming attribution** — If a response stream is interrupted (user cancels, network drops), how many tokens were actually delivered vs billed? Track the last complete chunk before interruption.

13. **Provider type discovery** — When a user adds a custom OpenAI-compatible endpoint, should the UI attempt to auto-detect the provider type (vLLM vs Ollama vs LiteLLM) or always default to `custom`?

## Migration Path — From CLI to UI

### Philosophy

The UI is a management layer over Hermes, not a replacement. Every CLI workflow must continue to work. The migration design follows three rules:

1. **No breakage** — Launching the UI does not change any existing file. Nothing is moved, renamed, or rewritten without explicit user action.
2. **CLI still works** — After migration, every `hermes` command functions identically. The UI is additive.
3. **No split-brain** — The user should never have to wonder "did I edit this in CLI or UI?" When both manage the same data, they share the same files.

### Inventory — What Exists Today

| Surface | Location | Format | Sync Strategy |
|---------|----------|--------|---------------|
| Main config | `~/.hermes/config.yaml` | YAML | Dual-write |
| Environment secrets | `~/.hermes/.env` | `KEY=value` | Read-only (UI never writes .env) |
| Auth/credential pools | `~/.hermes/auth.json` | JSON | Read-only (UI replicates into its own encrypted store) |
| Profiles | `~/.hermes/profiles/<name>/` | Config.yaml + .env + skills/ + sessions/ + memories/ | One-time import (personality creation) |
| MCP server configs | `~/.hermes/config.yaml` → `mcp_servers` key | YAML | Dual-write |
| Custom providers | `~/.hermes/config.yaml` → `custom_providers` key | YAML | Dual-write |
| Cron jobs | `~/.hermes/cron/cronjobs.db` | SQLite | Dual-write |
| Skills | `~/.hermes/skills/<name>/SKILL.md` | Markdown | Read-only reference |
| Session history | `~/.hermes/sessions/sessions.db` | SQLite | Read-only (UI adds its own session store alongside) |
| Memories | `~/.hermes/memories/MEMORY.md`, `USER.md` | Markdown | Read-only (UI personalities have their own memory store) |
| OAuth tokens | `~/.hermes/auth.json` (and cached http-tokens/) | JSON + HTTP cookies | Read-only |
| Plugins | `~/.hermes/plugins/` | Python pkgs + config | Read-only (UI displays but doesn't manage) |
| Curator telemetry | `~/.hermes/skills/.usage.json` | JSON | Read-only (pass-through to Hermes) |

### Sync Strategy Breakdown

#### Dual-Write Surfaces

The UI writes directly to the same files Hermes CLI reads. This is how coexistence works:

**config.yaml (providers + MCP):**
```
UI saves personality with provider=openrouter, model=gpt-4o
  → UI writes to ~/.hermes/config.yaml:
      model:
        default: gpt-4o
        provider: openrouter
  → Next `hermes` CLI invocation picks up the change automatically
  → Next UI page load reads it back from config.yaml

UI adds MCP server "postgres-db"
  → UI writes to ~/.hermes/config.yaml:
      mcp_servers:
        - name: postgres-db
          command: npx
          args: ["@anthropic/mcp-postgres", "..."]
  → `hermes mcp list` sees it
  → UI reads it back on next load
```

**Cron SQLite:**
```
UI creates cron job
  → UI opens ~/.hermes/cron/cronjobs.db directly (same SQLite schema)
  → `hermes cron list` shows the job
  → Scheduler runs it regardless of who created it
```

**Risks:**
- **Concurrent write race** — CLI saves config.yaml while UI has a dirty in-memory copy. Mitigation: the UI reads config.yaml fresh before every write (no stale in-memory cache of the raw YAML), and writes use atomic tempfile+rename.
- **YAML comment loss** — Hermes' `config set` preserves comments. The UI must use ruamel.yaml (comment-aware) or take the same approach: read → modify AST → write, never dump/reload.
- **Cron DB lock** — The scheduler holds a write lock; UI write must use `WAL` mode and retry on `SQLITE_BUSY`.

#### One-Time Import Surfaces

**Profiles → Personalities:**
```
First-boot inventory scans ~/.hermes/profiles/
For each profile named "researcher":
  - Read its config.yaml (provider, model, system prompt, skills, toolsets)
  - Present to user: "Import profile 'researcher' as a personality?"
  - On yes: create a new personality with those settings
  - Profile remains untouched on disk (can still use `hermes profile use researcher`)
  - The new personality is a snapshot, not a live link
```

**Existing MCP servers in config.yaml:**
```
At first boot, UI scans config.yaml for any mcp_servers entries.
Lists them as "discovered" with an "Adopt" button.
On adoption: creates an MCP server record in the UI's managed store.
Config.yaml entry is left in place (UI will dual-write from now on).
```

**Existing cron jobs in cron SQLite:**
```
UI opens the existing cron.db, reads all jobs, displays them in the Cron Jobs tab.
Jobs remain in the original DB — UI and CLI share the same SQLite file.
No adoption step needed; it's the same database.
```

#### Read-Only Surfaces

Session history, memories, and skills stay where they are. The UI doesn't touch them. It maintains its own session store for personality conversations and its own memory bank. The existing Hermes sessions/memories/skills are available for reference but managed exclusively through the CLI.

### First-Boot Flow

```
1. UI server starts

2. Discovery Phase:
   a. Read ~/.hermes/config.yaml → extract model.provider, model.default,
      custom_providers, mcp_servers, fallback_providers, auxiliary.*
   b. List ~/.hermes/profiles/ → each subdirectory = one Hermes profile
   c. Open ~/.hermes/cron/cronjobs.db → existing cron jobs
   d. List ~/.hermes/skills/ → installed skills
   e. Read ~/.hermes/auth.json → known credential pools

3. Present Inventory Screen (web page):
   "Found 2 MCP servers, 3 profiles, 4 cron jobs, 15 skills"

   [ ] Adopt MCP server "postgres-db"
   [ ] Adopt MCP server "web-scraper"
   [ ] Import profile "researcher" as personality
   [ ] Import profile "coder" as personality
   [ ] Import profile "analyst" as personality
   [ ] Import cron jobs to UI management
   [ ] Scan credential pools into provider manager

   [One-time setup] [Skip all]

4. User confirms selections → UI performs import actions

5. First personality created → user is taken to chat view
```

After first boot, the inventory screen can be re-triggered from Settings to pick up any newly created CLI configs.

### Config Coexistence Rules

Once the UI is live, writes flow both ways:

| Action | What happens |
|--------|-------------|
| User edits provider in UI | UI updates config.yaml → `model.provider` and `custom_providers` as needed |
| User runs `hermes config set model.default gpt-4o` | Next UI page load detects the config.yaml change and refreshes the in-memory view |
| User adds MCP server via `hermes mcp add` | Next UI page load shows it in MCP view as "discovered" (no managed record yet) |
| User edits cron via `hermes cron` | UI picks up changes on next load (same SQLite DB) |
| User creates personality in UI | Written to UI's SQLite DB + exported as a proxy profile under `~/.hermes/profiles/.ui/personality-id/` so `hermes` CLI can run it via `hermes --profile .ui/researcher` |
| User runs `hermes profile use researcher` (pre-existing CLI profile) | UI sees an unmanaged profile in Discovery view, offers to import |

The key invariant: **config.yaml and cron.db are the source of truth** for provider, MCP, and cron data. The UI's SQLite is a cache/index on top, rebuilt on reads if the file modification time has changed.

### Reverse Migration — UI → CLI

A personality created in the UI can be exported as a Hermes profile:

```
UI → "Export as Hermes Profile"
  → Creates ~/.hermes/profiles/.ui-export/<personality-id>/
  → Writes config.yaml, symlinks skills, sets model/provider
  → User runs: hermes --profile .ui-export/researcher
```

The UI also exposes a bulk export endpoint (`/config/export` → downloadable YAML/JSON/tar.gz bundle containing all personalities, MCP configs, and cron jobs).

### Rollback Plan

If the user decides the UI isn't for them:

1. Stop the UI server
2. `~/.hermes/config.yaml` is untouched from original (UI wrote to it, but the same content `hermes config set` would produce)
3. Cron jobs still work (same SQLite DB)
4. UI-specific data lives in a self-contained directory: `~/.hermes/personalities-ui/` (SQLite DB + personality JSON + encrypted key store)
5. Remove that directory → all UI artifacts gone, CLI unchanged

The UI stores all its managed data under a single directory, never scattering files into existing Hermes paths. Config.yaml writes are the only cross-contamination, and those are identical to what `hermes config set` would have produced anyway.

### What About Sessions & Memory?

| Concern | Answer |
|---------|--------|
| Existing Hermes sessions | Stay in `~/.hermes/sessions/sessions.db`. UI doesn't touch them. UI conversations go into the UI's own `messages` table. A future feature could import them. |
| Personality memory | Each personality uses its own memory provider (Hindsight, Honcho, etc.) per its config. Separate from the CLI profile's memory. |
| CLI profile memories | Untouched. The personality that came from an imported profile starts fresh unless the user explicitly copies the memories over. |

### Summary: The One Rule

> The UI writes the same bytes to the same paths that `hermes config set` or `hermes cron create` would write.

If you can do it with a CLI command, the UI can do it via the same file/SQLite write. Everything else (personalities, token usage, workflows, UI prefs) is additive — stored separately, never interfering with Hermes' existing state.

## Implementation Phases

### Phase 0 — Discovery & Inventory (1 day)

Goal: UI can read all existing Hermes configs, display them, and offer one-time import.

- [ ] Inventory scanner: read config.yaml, list profiles, open cron.db, list skills
- [ ] Inventory screen frontend: discovered items with import/ignore toggles
- [ ] Import profile → personality converter (reads profile config.yaml, builds personality JSON)
- [ ] Adopt MCP server flow (reads config.yaml → creates managed MCP server record)
- [ ] Dual-write to config.yaml for provider/MCP changes
- [ ] Cron SQLite read/write layer (open existing cron.db, compatible schema)
- [ ] Atomic YAML writer with ruamel.yaml (preserves comments, no comment loss)
- [ ] Rollback directory structure: `~/.hermes/personalities-ui/`

### Phase 1 — Skeleton (1-2 days)

Goal: Working streaming chat with one personality. No config editor, no MCP, no tokens, no provider management.

- [ ] FastAPI app with single WebSocket endpoint
- [ ] Streaming Bridge in SDK mode (patch `run_agent.py` or wrap `AIAgent`)
- [ ] Emit events: `turn_start`, `token`, `tool_call`, `tool_result`, `response`, `turn_end`
- [ ] Basic SvelteKit frontend: single chat view, hardcoded personality
- [ ] Wire `WS /ws` with hardcoded personality config
- [ ] Handle reconnection and session persistence

### Phase 2 — Multi-Personality + MCP + Tokens + Provider Manager (5-8 days)

Goal: Personality CRUD, MCP management, token tracking, provider management, cron jobs all operational.

- [ ] Personality Manager: CRUD endpoints, config merge logic, SQLite schema
- [ ] Personality sidebar in frontend (list, switch, create)
- [ ] Personality Config Editor UI (all fields except provider manager integration)
- [ ] MCP Server Manager: connection pool, lifecycle, health monitor
- [ ] MCP Management View in frontend (add/edit/test/assign)
- [ ] Personality-to-MCP assignment in config editor
- [ ] Token Tracker: capture hook, pricing table, write to SQLite
- [ ] Token usage events in Streaming Bridge (`usage` type)
- [ ] Token badge on chat messages in frontend
- [ ] Provider Manager: CRUD endpoints, encrypted key storage, model discovery
- [ ] Provider Management View in frontend (add/edit/test/discover models)
- [ ] Model browser in frontend (search/filter discovered models)
- [ ] Auxiliary task provider mapping grid
- [ ] Test connection flows (provider test button with progress indicator)
- [ ] Persona provider/model selector pulling from Provider Manager
- [ ] Cron Scheduler: create/edit/delete jobs, test-run, pause/resume
- [ ] Cron Jobs tab in frontend (schedule list, next-run, status indicators)

### Phase 3 — UX Polish + Workflows (3-5 days)

Goal: Full chat experience with tool call rendering, hotkeys, MCP tool display, workflow builder.

- [ ] Tool call collapsible cards in chat view
- [ ] Tool result rendering with truncation indicator
- [ ] Thinking block expand/collapse
- [ ] Keyboard shortcuts (Ctrl+Enter send, Esc cancel, Ctrl+P new personality)
- [ ] MCP tool schema browser in server detail view
- [ ] Personality import/export (JSON/YAML)
- [ ] Session search within personality
- [ ] Provider model cache refresh button
- [ ] Personality inheritance model (base profile → overrides)
- [ ] Workflow Engine: DAG step CRUD, step ordering, condition branching
- [ ] Workflow Pipeline View: drag/connect step editor
- [ ] Cron + Workflow integration (jobs trigger workflows, workflows contain cron steps)
- [ ] Job History & Logs: execution timeline, per-tick status

### Phase 4 — Advanced Views (2-3 days)

Goal: Side-by-side comparisons, chain mode, usage dashboard, budget enforcement, credential pools.

- [ ] Side-by-side chat (two personalities, same prompt)
- [ ] Chain mode (output of A feeds into B)
- [ ] Arena mode (same prompt to N personalities, compare responses)
- [ ] Token Usage Dashboard (time-series chart, per-model breakdown)
- [ ] Budget enforcement (pre-flight check, budget_exceeded event, block UI)
- [ ] Budget progress bars in sidebar
- [ ] Usage export (CSV/JSON/PDF)
- [ ] Provider credential pool management UI
- [ ] Provider auxiliary task grid editor
- [ ] Budget notifications (in-chat alert at notify_at_pct)
- [ ] Cron job detail view with execution timeline (green/red ticks)

### Phase 5 — Production (2-3 days)

Goal: Auth, containerization, monitoring, cost alerting, cross-system dashboard.

- [ ] Authentication (session tokens, SSO via Hermes OAuth)
- [ ] Docker Compose (FastAPI + SvelteKit + SQLite + Caddy/nginx)
- [ ] API key scoping (read-only vs admin keys)
- [ ] Provider key health monitoring (stale key detection, auto-failover)
- [ ] Background tasks: session archival, usage summary rollup, provider model cache refresh
- [ ] Multi-user support (user isolation, per-user personalities)
- [ ] Audit log for config changes
- [ ] Grafana/Prometheus metrics (requests, tokens, latency, error rates)
- [ ] MCP orphan cleanup daemon
- [ ] Cron + workflow overview on dashboard (next N runs, recent completions, failure alerts)

**Total estimated development time: 14-22 days for a solo developer (includes Phase 0 discovery/inventory).**
