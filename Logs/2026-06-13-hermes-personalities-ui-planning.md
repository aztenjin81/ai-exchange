---
type: log
status: active
date: 2026-06-13
tags: [hermes, web-ui, personalities, planning]
---

# Session: Hermes Personalities Web UI Planning

Planned and documented the architecture for a web-based chat UI that leverages multiple Hermes agent personalities, inspired by Open WebUI.

## Created Notes

- [[Hermes-Personalities-UI]] — Full architecture document (backend, frontend, data flow, hard parts, implementation phases)
- [[Hermes-Profiles]] — Reference on the Hermes profile system that powers each personality

## Key Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend | FastAPI | Async, WebSocket-native, Python |
| Frontend | SvelteKit | Small bundle, native reactivity |
| Hermes integration | SDK mode (in-process import) | Fastest path, no subprocess overhead |
| Streaming | WebSocket JSON events | Bidirectional, structured event types |
| Personality storage | JSON files | Easy to edit, git-friendly |
| Session history | SQLite | Durable, survives restart |

## Streaming Event Types

Each agent loop turn emits structured events via WebSocket:
- `thinking` — agent reasoning text
- `tool_call` — tool name + arguments
- `tool_result` — tool output (truncated)
- `response` — final user-facing message
- `done` — session turn complete
- `error` — failure

## Hard Parts Identified

1. **Streaming** — Hermes is turn-based; needs event hooking in the SDK
2. **Session isolation** — N personalities = N isolated agent states
3. **Resource cost** — Each personality holds a full context window
4. **Tool output UX** — Large tool outputs need smart truncation + UI

## Implementation Phases

| Phase | Effort | Deliverable |
|-------|--------|-------------|
| 1 — Skeleton | 1-2 days | End-to-end prototype, one hardcoded personality |
| 2 — Multi-personality | 2-3 days | Switchable personalities, configs, history |
| 3 — UX Polish | 2-3 days | Tool rendering, streaming indicators, hotkeys |
| 4 — Advanced views | 2-3 days | Side-by-side, chain, arena modes |
| 5 — Production | 2-3 days | Auth, Docker, monitoring, docs |

## Related

- [[Hermes-Personalities-UI]]
- [[Hermes-Profiles]]
