---
type: reference
status: draft
date: 2026-06-13
tags: [hermes, web-ui, architecture, personalities, project-plan]
---

# Hermes Personalities Web UI

A web-based chat interface inspired by Open WebUI, but each "model switch" changes the entire Hermes agent personality — model, provider, system prompt, skills, toolset, and memory bank.

## Core Concept

Open WebUI lets you switch between LLM models. This lets you switch between *agent configurations*. Each personality is a complete Hermes profile running in its own isolated session.

```
User Message
  |
  v
[Personality Selector] ---> Personality A (profile: dev)
                           Personality B (profile: research)
                           Personality C (profile: writing)
  |
  v
[Hermes Agent Loop] ---> Think -> Tool -> Result -> Think -> ... -> Respond
  |
  v
[Stream to UI]
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   Frontend (SvelteKit)           │
│  ┌──────────┐  ┌────────────┐  ┌─────────────┐  │
│  │ Chat View │  │Personality │  │  Config     │  │
│  │ (streams) │  │  Sidebar   │  │  Editor     │  │
│  └────┬─────┘  └─────┬──────┘  └──────┬──────┘  │
└───────┼──────────────┼────────────────┼──────────┘
        │ WebSocket    │ REST           │ REST
┌───────┼──────────────┼────────────────┼──────────┐
│       v              v                v          │
|               Backend (FastAPI)                   |
|  ┌──────────┐  ┌────────────┐  ┌─────────────┐  |
|  │ Streaming│  │ Personality│  │  MCP Server │  |
|  │ Bridge   │  │ Manager    │  │  Manager    │  |
|  └────┬─────┘  └─────┬──────┘  └──────┬──────┘  |
|       │              │                │          |
|  ┌────┴──────────────┴────────────────┴──────┐   |
|  │         Hermes SDK / Agent Runner          │   |
|  │  (imported in-process, profile per call)   │   |
|  └────┬──────────────────────────────────────┘   |
|       │                                          |
|  ┌────┴──────────────────────────────────────┐   |
|  │       MCP Connection Pool                 │   |
|  │  ┌─────┐ ┌─────┐ ┌─────┐                 │   |
|  │  │ MCP │ │ MCP │ │ MCP │  ...            │   |
|  │  │ Srv1│ │ Srv2│ │ Srv3│                 │   |
|  │  └─────┘ └─────┘ └─────┘                 │   |
|  └──────────────────────────────────────────-┘   |
└───────────────────────────────────────────────────┘
```

## Backend Components

### FastAPI Server
Async server with WebSocket support. Routes:

| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/personalities | List all personalities |
| POST | /api/personalities | Create personality |
| GET | /api/personalities/{id} | Get personality config |
| PUT | /api/personalities/{id} | Update personality |
| DELETE | /api/personalities/{id} | Delete personality |
| GET | /api/personalities/{id}/sessions | List sessions |
| POST | /api/personalities/{id}/sessions | New session |
| WS | /ws/{personality_id}/{session_id} | Streaming chat |
| GET | /api/mcp/servers | List all MCP servers |
| POST | /api/mcp/servers | Add MCP server config |
| GET | /api/mcp/servers/{id} | Get MCP server config |
| PUT | /api/mcp/servers/{id} | Update MCP server config |
| DELETE | /api/mcp/servers/{id} | Delete MCP server config |
| GET | /api/mcp/servers/{id}/status | Get connection status |
| POST | /api/mcp/servers/{id}/test | Test connection |
| GET | /api/mcp/servers/{id}/tools | List available tools |
| POST | /api/mcp/servers/{id}/reload | Reload connection |
| GET | /api/personalities/{id}/mcp | Get assigned MCP servers |
| PUT | /api/personalities/{id}/mcp | Set assigned MCP servers |

### Personality Manager
Maps personality IDs to configs. Each personality stores:
- `name` — display name
- `profile` — Hermes profile name (from ~/.hermes/profiles/)
- `model` — model override (optional)
- `provider` — provider override (optional)
- `system_prompt` — system prompt override (optional)
- `enabled_skills` — list of skill names to load
- `toolset` — toolset restrictions
- `temperature` — model temperature
- `avatar` — color/icon for UI
- `assigned_mcp_servers` — list of MCP server IDs to connect for this personality

Configs stored as JSON in a data directory (e.g. `~/.hermes/personalities/`).

### Session Router
Manages active conversations per personality. In-memory store with SQLite persistence:
- `{personality_id}:{session_id}` maps to state object
- State includes: message history, tool output cache, session metadata
- Sessions auto-expire after inactivity (configurable TTL)
- SQLite fallback for restoring on restart

### MCP Server Manager

Manages the lifecycle, discovery, and personality-to-server mapping for MCP connections. This is the most architecturally significant component because Hermes currently handles MCP globally in `config.yaml` — the UI needs to manage it independently.

**MCP Server Config Model (stored as JSON)**

```json
{
  "id": "filesystem-1",
  "name": "Project Files",
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/projects"],
  "env": {},
  "timeout": 120,
  "connect_timeout": 60,
  "auto_start": true,
  "tags": ["filesystem", "local"]
}
```

Or for HTTP transport:

```json
{
  "id": "remote-api",
  "name": "Company API",
  "transport": "http",
  "url": "https://mcp.internal.company.com/mcp",
  "headers": {
    "Authorization": "Bearer sk-..."
  },
  "timeout": 300,
  "connect_timeout": 30,
  "auto_start": true,
  "tags": ["api", "remote"]
}
```

#### Connection Lifecycle

```
                  ┌──────────────┐
                  │  Config DB   │
                  └──────┬───────┘
                         │
              ┌──────────v──────────┐
              │  Connection Pool    │
              │  (in-memory map)    │
              └──────┬──────────────┘
                     │
       ┌─────────────┼─────────────┐
       │             │             │
  ┌────v────┐  ┌────v────┐  ┌────v────┐
  │ MCP Srv │  │ MCP Srv │  │ MCP Srv │
  │ (stdio) │  │ (HTTP)  │  │ (stdio) │
  │  PID: X │  │  conn Y │  │  PID: Z │
  └─────────┘  └─────────┘  └─────────┘
       │             │             │
       └─────────────┼─────────────┘
                     │
              ┌──────v──────┐
              │  Health     │
              │  Monitor    │
              │  (pings/sec)│
              └─────────────┘
```

- **On server add:** config saved to DB. If `auto_start: true`, immediately spawn the subprocess / open HTTP connection and attempt handshake.
- **On personality activate:** the agent runner loads only the MCP servers assigned to that personality. Servers shared across personalities use the same connection (reference-counted).
- **On server update:** config saved. Connection is gracefully closed and re-established with new params.
- **On server delete:** config removed. Connection closed. All personalities that reference it get their `assigned_mcp_servers` list cleaned up.
- **Health monitoring:** background task pings each server connection every 30 seconds. Dead connections trigger reconnect with exponential backoff (1s, 2s, 4s, 8s, 16s, cap at 60s, max 5 retries).
- **Sharing vs isolation:** same server assigned to 3 personalities = 1 connection, reference-counted. Personality-specific MCP servers get their own process. The `id` field in config is the dedup key.

#### Tool Discovery Flow

```
1. MCP server connects → backend calls `list_tools()`
2. Backend caches tool schemas in memory (keyed by server ID)
3. When a personality is activated:
   a. Look up assigned server IDs
   b. For each, check if connection is alive (start if auto_start)
   c. Fetch cached tool schemas
   d. Inject them into the agent's tool registry with `mcp_{server}_{tool}` naming
4. Tool injection is scoped to that personality's agent session — not global
5. When personality is deactivated (user switches), tools are removed from the agent's registry
```

**Schema caching is critical:** MCP tool schemas can be large (77 tools × ~2.5KB each = ~200KB). Without caching, every personality activation triggers a full re-discovery. With caching, only the first activation of a new/changed server triggers discovery.

#### Backend Implementation

```python
class MCPServerManager:
    """Manages MCP server connections, lifecycle, and personality mapping."""

    def __init__(self, db: Database):
        self.db = db
        self.connections: dict[str, MCPConnection] = {}  # server_id -> connection
        self.tool_cache: dict[str, list[ToolSchema]] = {}  # server_id -> tools
        self.ref_counts: dict[str, int] = {}  # server_id -> personality count
        self._health_task: asyncio.Task | None = None

    async def start(self):
        """Load all servers from DB, start auto_start ones."""
        servers = await self.db.get_all_mcp_servers()
        for srv in servers:
            if srv.auto_start:
                await self._connect(srv)

    async def assign_to_personality(self, server_id: str, personality_id: str):
        """Increment ref count, start if not running."""
        self.ref_counts[server_id] = self.ref_counts.get(server_id, 0) + 1
        if server_id not in self.connections:
            srv = await self.db.get_mcp_server(server_id)
            await self._connect(srv)

    async def release_from_personality(self, server_id: str, personality_id: str):
        """Decrement ref count, disconnect if zero."""
        self.ref_counts[server_id] -= 1
        if self.ref_counts[server_id] <= 0:
            await self._disconnect(server_id)

    async def get_tools_for_personality(self, personality_id: str) -> list[ToolSchema]:
        """Get all MCP tools available to a personality."""
        personality = await self.db.get_personality(personality_id)
        tools = []
        for srv_id in personality.assigned_mcp_servers:
            if srv_id in self.tool_cache:
                tools.extend(self.tool_cache[srv_id])
        return tools

    async def test_connection(self, config: MCPServerConfig) -> TestResult:
        """Test an MCP server config without persisting it."""
        # Spawn/connect, run list_tools, disconnect, return status + tool count
        ...

    async def reload_server(self, server_id: str):
        """Graceful reconnect — close old, start new with same config."""
        await self._disconnect(server_id)
        srv = await self.db.get_mcp_server(server_id)
        await self._connect(srv)
```

#### Personality-to-MCP Assignment Rules

| Scenario | Behavior |
|----------|----------|
| Personality A has server S, B also has S | One connection, shared. Ref count = 2 |
| Personality A has server S1, B has server S2 | Two connections, independent |
| Server S dies | Health monitor detects, attempts reconnect. All personalities sharing S lose MCP tools during outage |
| Personality A is deleted | All its MCP ref counts decremented. Zero-count servers disconnected |
| Server S config updated | Connection restarted. Tool cache invalidated for S. Active personalities get fresh tools on next turn |
| Server S added to personality A mid-session | Connection established (or ref count bumped), tools injected into agent on next turn |

### Streaming Bridge

The core challenge. Hermes runs a turn-based agent loop: the agent thinks, calls tools, gets results, thinks again, and eventually produces a response. The bridge captures this loop and emits structured events.

**Event schema (WebSocket JSON frames):**

```json
{"type": "thinking", "content": "I need to look up the docs..."}
{"type": "tool_call", "id": "call_1", "tool": "web_search", "args": {"query": "..."}}
{"type": "tool_result", "id": "call_1", "content": "Search results...", "truncated": true}
{"type": "thinking", "content": "Based on the results..."}
{"type": "response", "content": "Here's what I found..."}
{"type": "done", "session_id": "..."}
{"type": "error", "message": "Tool timed out"}
```

**Implementation:** Import Hermes' agent runner as a Python library. Hook into the event emitter system to intercept each stage of the loop. Pipe events through an async generator that feeds the WebSocket.

```python
# Pseudocode
from hermes.agent import AgentRunner

async def run_agent_turn(personality, history, message):
    runner = AgentRunner(profile=personality.profile)
    async for event in runner.stream(message, history=history):
        await websocket.send_json(event.to_dict())
        if event.type == "response":
            persist_to_history(event.content)
```

## Frontend Components

### Tech Stack
- **Framework:** SvelteKit — smaller bundle, native reactivity, simpler than React for real-time UIs
- **Styling:** Tailwind CSS — rapid iteration, dark/light theme via class toggle
- **State:** Svelte stores + localStorage for personality configs (cache)

### Views

**Chat View**
- Scrollable message list with personality color-coding
- Each message shows: avatar, name, timestamp, content
- Streaming responses render token-by-token as they arrive
- Tool calls shown as expandable cards between messages
- Tool result preview (collapsible, with size-based truncation)
- Input bar with: text area, send button, personality quick-switch dropdown

**Personality Sidebar**
- Persistent left sidebar listing all personalities
- Active personality highlighted with accent color
- Status indicator (online/idle/error per personality)
- Quick-switch via click or hotkey (Cmd+1-9)
- Add / edit / delete controls at bottom
- Drag to reorder

**Personality Config Editor**
- Modal or side panel
- Fields: Name, Avatar (color picker + emoji), Model, Provider
- System prompt as code editor (monospace, syntax highlight)
- Skill toggles: searchable list of available skills with enable/disable
- Toolset selection: checkboxes for tool categories
- **MCP Server assignment: multi-select dropdown of configured MCP servers**
- Temperature slider (0.0 - 2.0)
- "Test personality" button — sends test message to confirm config works

**MCP Management View**
- Dedicated page or modal (tab in sidebar or separate route)
- Lists all configured MCP servers with status indicators:
  - 🟢 Connected (tools available)
  - 🟡 Starting (connection in progress)
  - 🔴 Error (failed to connect, shows error message)
  - ⚪ Disabled (auto_start off, not connected)
- Each server card shows: name, transport type (stdio/HTTP), tags, connection time, tool count
- **Add Server form** with fields:
  - Name, ID (auto-generated from name)
  - Transport: Stdio (command + args + env vars) or HTTP (URL + headers)
  - Timeout and connect_timeout
  - Auto-start toggle
  - Tags (freeform, for organization)
  - "Test Connection" button before saving
- **Edit Server:** same form, pre-populated
- **Server detail view:** shows full config + live status + list of discovered tools (name, description, schema size)
  - Per-tool "copy name" button (e.g. `mcp_filesystem_read_file`)
  - Reload connection button
  - Delete button (with cascading personality cleanup warning)
- **Personality assignment section in detail view:** shows which personalities use this server, click through to edit that personality
- **Bulk actions:** test all, reload all, start all, stop all

**Multi-Chat Views (Phase 4)**
- **Side-by-side:** Two personalities receive the same prompt simultaneously. Responses stream in parallel. User can compare and vote/tag the better one.
- **Chain:** Output of Personality A is auto-injected as input to Personality B. Configurable pipeline (A → B → C).
- **Arena:** N personalities respond to the same prompt. User sees all responses and selects the best. Tracks win/loss stats per personality.

### Tool Call Rendering
Hermes tools produce structured output that needs dedicated UI:

```
┌─────────────────────────────────┐
│ 🔧 web_search                   │ <- tool name + icon
│ Query: "latest python version"  │ <- args (truncated)
│ ┌─────────────────────────────┐ │
│ │ ✓ Done (0.8s)              │ │ <- status + duration
│ │ ─────────────────────────── │ │
│ │ Python 3.13.2 released...  │ │ <- result preview
│ │ Show more ▾                │ │ <- expand/collapse
│ └─────────────────────────────┘ │
└─────────────────────────────────┘
```

Tool cards are collapsible by default. Large results show first 5 lines with "Show more" button.

## Data Flow (End-to-End)

```
1. User types message in Personality A's chat
2. Frontend sends via WebSocket:
   {personality_id: "A", session_id: "abc123", message: "..."}
3. Backend resolves Personality A config:
   - profile: "research"
   - provider: "openrouter"
   - model: "anthropic/claude-sonnet-4"
   - skills: ["web_search", "arxiv"]
   - temperature: 0.3
4. Backend loads conversation history from session store
5. Backend calls Hermes SDK with config + history + message
6. Agent loop runs, emitting events:
   - thinking → WebSocket
   - tool_call → WebSocket (frontend shows running state)
   - tool_result → WebSocket (frontend shows result)
   - thinking → WebSocket
   - response → WebSocket (frontend streams tokens)
   - done → WebSocket
7. Backend persists response to session store
8. Frontend appends final message to chat view
```

## State & Persistence

| Data | Store | Why |
|------|-------|-----|
| Personality configs | JSON files on disk | Easy to edit manually, git-friendly |
| MCP server configs | JSON files on disk (separate from personality) | Same rationale — git-friendly, independent lifecycle |
| Session history | SQLite | Durable, queryable, survives restart |
| Active sessions | In-memory dict | Fast, no DB overhead per message |
| MCP tool schema cache | In-memory dict | Prevents re-discovery per turn; invalidated on server update |
| Tool output cache | In-memory (per session) | Ephemeral, cleaned on session end |

SQLite schema:
```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    personality_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- 'user', 'assistant', 'tool'
    content TEXT,
    tool_calls JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE mcp_servers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    transport TEXT NOT NULL CHECK(transport IN ('stdio', 'http')),
    config JSON NOT NULL,  -- command/args/env for stdio, url/headers for http
    auto_start INTEGER DEFAULT 1,
    tags TEXT DEFAULT '[]',  -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE personality_mcp (
    personality_id TEXT NOT NULL,
    mcp_server_id TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    PRIMARY KEY (personality_id, mcp_server_id),
    FOREIGN KEY (personality_id) REFERENCES personalities(id) ON DELETE CASCADE,
    FOREIGN KEY (mcp_server_id) REFERENCES mcp_servers(id) ON DELETE CASCADE
);
```

## Hard Parts

### 1. Streaming from Hermes
Hermes' agent loop is synchronous and turn-based. It doesn't expose a streaming API. Approaches:

| Approach | Pros | Cons |
|----------|------|------|
| **SDK mode** — import Hermes in-process, hook event emitter | Fastest, full control, no subprocess overhead | Requires Hermes to expose internal event hooks (may need patching) |
| **Subprocess mode** — `hermes run --profile X`, parse stdout | Clean isolation, uses existing CLI | Slow (Python startup per turn), hard to parse intermediate state |
| **Persistent process** — spawn Hermes per personality, communicate via pipes | Good isolation, no startup per turn | Complex IPC, resource-heavy per personality |

**Recommended:** SDK mode. Patch Hermes' `AgentRunner` to accept an event callback. If that's too invasive, fall back to persistent process mode using Hermes' WebSocket server (if available) or a custom loop.

### 2. Session Isolation
Each personality's session must not leak state to another. Mitigations:
- Separate in-memory state objects per `{personality, session}` key
- No shared globals in the agent runner
- Clear tool output cache between sessions
- If using subprocess mode: one process per session, kill on timeout

### 3. Resource Cost
N active personalities = N × full agent context window. For a 128K context with 4 personalities: ~512K tokens in RAM minimum, plus tool outputs. Mitigations:
- Aggressive session timeout (15 min inactivity → gc)
- Tool output truncation (keep last 5 results, not all)
- Context window limit per personality configurable
- One personality active at a time (suspend others to disk/DB)

### 4. Tool Output UX
Tool outputs can be megabytes (file reads, DB queries, web page extracts). The UI must handle this gracefully:
- Server-side truncation with `truncated: true` flag
- Client-side collapsible cards with "show full" button (requests full content via separate API)
- Don't block the message stream waiting for large tool outputs

### 5. MCP Server Lifecycle & Isolation
MCP adds a whole new dimension of complexity:

| Challenge | Impact | Mitigation |
|-----------|--------|------------|
| **Process management** | MCP servers are long-lived subprocesses or HTTP connections that can crash, hang, or leak memory | Health monitor with reconnect; per-server timeout; max restart policy (e.g. 5 restarts in 5 min → flag as dead) |
| **Credential security** | API keys and tokens in MCP server `env` or `headers` stored in config DB | Encrypt sensitive fields at rest; env var interpolation from server environment; never expose credentials in API responses |
| **Tool injection timing** | MCP tools must be available before the agent runs but starting a server takes 1-30s | Warm-up on personality creation; lazy init with "starting" status in UI; server-level readiness check before agent turn starts |
| **Scoped tool registry** | Hermes registers MCP tools globally. Per-personality scoping requires modifying how tools are injected | In-process SDK mode can scope tools per agent runner instance. Subprocess/persistent modes need separate processes per personality |
| **Schema bloat** | Each MCP server adds KB of JSON schema to the agent's system prompt. 5 servers × 50 tools = 500+ tool schemas | Only inject tool schemas from the active personality's assigned servers. Consider a "tool use budget" per personality |
| **Hot-reload gap** | Hermes doesn't support hot-adding MCP servers — requires restart | The UI backend can work around this by managing MCP connections outside of Hermes' own MCP client, injecting tools directly into the agent's registry |

## Implementation Phases

### Phase 1 — Skeleton (1-2 days)
Goal: End-to-end working prototype with one hardcoded personality.

- [ ] FastAPI server with WebSocket endpoint
- [ ] SDK-mode integration with Hermes (hook into agent loop)
- [ ] Minimal SvelteKit chat UI (single personality, streaming response, tool cards)
- [ ] Verify end-to-end: type message → see agent think/tool/respond in real-time

### Phase 2 — Multi-Personality (2-3 days)
Goal: Switchable personalities with persistent configs and history.

- [ ] Personality CRUD API + JSON file storage
- [ ] Personality sidebar in UI with quick-switch
- [ ] Session isolation (per-personality state)
- [ ] SQLite history persistence
- [ ] Personality config editor (name, model, system prompt, skills)

### Phase 3 — UX Polish (2-3 days)
Goal: Production-quality single-user experience.

- [ ] Tool call rendering (expandable cards, status indicators, timing)
- [ ] Streaming indicators (pulsing cursor during thinking, tool progress bars)
- [ ] Error handling + retry (personality config error, tool timeout, network drop)
- [ ] Hotkeys (Cmd+1-9 switch personality, Cmd+Enter send)
- [ ] Dark/light theme toggle
- [ ] Keyboard-only navigation

### Phase 4 — Advanced Views (2-3 days)
Goal: Multi-personality workflows.

- [ ] Side-by-side comparison view
- [ ] Chain mode (output of A → input of B)
- [ ] Arena mode (N responses, vote on best)
- [ ] Personality import/export (JSON)

### Phase 5 — Production Ready (2-3 days)
Goal: Deployable, documented, maintainable.

- [ ] Auth (basic or token-based for non-localhost)
- [ ] Docker Compose (FastAPI + SvelteKit static build + optional nginx)
- [ ] Resource limits + monitoring (active sessions, memory usage)
- [ ] README + setup documentation
- [ ] Systemd service or docker-compose up

## Open Questions

1. **Personality inheritance** — Should a personality be a full independent config or override a base Hermes profile? (e.g. start from "research" profile, override model only)
2. **File uploads** — If a user uploads a file to Personality A, should it be available to Personality B? (Probably not — per-personality upload dirs)
3. **Voice** — Worth adding voice input (whisper) and output (TTS) per personality? (Phase 5+)
4. **Parallel execution** — For multi-chat views (side-by-side, arena), do we run N agent loops in parallel or sequentially? Parallel is faster but costs more resources.
5. **Hermes SDK hooks** — Does the current Hermes codebase expose clean hooks for event streaming, or do we need to patch it?

## Related

- [[Hermes-Profiles]] — existing Hermes profile system
- `README.md` — vault root (this document lives in the vault)
