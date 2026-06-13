"""SQLite database connection manager."""

from __future__ import annotations

from pathlib import Path

import aiosqlite


class Database:
    """Thin wrapper around aiosqlite with migration support."""

    def __init__(self) -> None:
        self._conn: aiosqlite.Connection | None = None

    async def connect(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(db_path))
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected — call connect() first")
        return self._conn

    async def run_migrations(self) -> None:
        """Create tables if they don't exist."""
        migrations = [
            # Personalities
            """
            CREATE TABLE IF NOT EXISTS personalities (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                system_prompt TEXT DEFAULT '',
                model       TEXT DEFAULT '',
                provider_id TEXT DEFAULT '',
                avatar      TEXT DEFAULT '🤖',
                token_budget_total INTEGER DEFAULT 0,
                token_budget_cost   REAL DEFAULT 0.0,
                mcp_server_ids TEXT DEFAULT '[]',
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            # Chat sessions
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id              TEXT PRIMARY KEY,
                personality_id  TEXT NOT NULL REFERENCES personalities(id) ON DELETE CASCADE,
                title           TEXT DEFAULT '',
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            # Messages
            """
            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                role        TEXT NOT NULL CHECK(role IN ('user','assistant','tool','system')),
                content     TEXT NOT NULL,
                tool_calls  TEXT DEFAULT '[]',
                tokens_in   INTEGER DEFAULT 0,
                tokens_out  INTEGER DEFAULT 0,
                cost        REAL DEFAULT 0.0,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            # Providers
            """
            CREATE TABLE IF NOT EXISTS providers (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                type        TEXT NOT NULL CHECK(type IN ('openai','anthropic','openrouter','ollama','vllm','custom')),
                base_url    TEXT DEFAULT '',
                api_key_enc TEXT DEFAULT '',
                models      TEXT DEFAULT '[]',
                note        TEXT DEFAULT '',
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            # MCP servers
            """
            CREATE TABLE IF NOT EXISTS mcp_servers (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                transport   TEXT NOT NULL CHECK(transport IN ('stdio','http')),
                command     TEXT DEFAULT '',
                args        TEXT DEFAULT '[]',
                env         TEXT DEFAULT '{}',
                url         TEXT DEFAULT '',
                enabled     INTEGER DEFAULT 1,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            # Cron jobs
            """
            CREATE TABLE IF NOT EXISTS cron_jobs (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                schedule        TEXT NOT NULL,
                personality_id  TEXT REFERENCES personalities(id) ON DELETE SET NULL,
                prompt          TEXT DEFAULT '',
                skills          TEXT DEFAULT '[]',
                no_agent        INTEGER DEFAULT 0,
                script_path     TEXT DEFAULT '',
                enabled         INTEGER DEFAULT 1,
                delivery_target TEXT DEFAULT '',
                model_override  TEXT DEFAULT '',
                workdir         TEXT DEFAULT '',
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            # Workflow definitions
            """
            CREATE TABLE IF NOT EXISTS workflows (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                enabled     INTEGER DEFAULT 1,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            # Workflow steps
            """
            CREATE TABLE IF NOT EXISTS workflow_steps (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
                step_order  INTEGER NOT NULL,
                job_id      TEXT REFERENCES cron_jobs(id) ON DELETE SET NULL,
                depends_on  TEXT DEFAULT '',
                condition   TEXT DEFAULT '',
                on_success  TEXT DEFAULT 'next',
                on_failure  TEXT DEFAULT 'stop',
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(workflow_id, step_order)
            )
            """,
            # Cron job execution history
            """
            CREATE TABLE IF NOT EXISTS cron_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                cron_id     TEXT NOT NULL REFERENCES cron_jobs(id) ON DELETE CASCADE,
                status      TEXT NOT NULL CHECK(status IN ('success','error','timeout')),
                duration_ms INTEGER DEFAULT 0,
                output      TEXT DEFAULT '',
                error       TEXT DEFAULT '',
                started_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            # Token usage log
            """
            CREATE TABLE IF NOT EXISTS token_usage (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                personality_id  TEXT REFERENCES personalities(id) ON DELETE SET NULL,
                session_id      TEXT REFERENCES sessions(id) ON DELETE SET NULL,
                provider        TEXT NOT NULL,
                model           TEXT NOT NULL,
                prompt_tokens   INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                cost            REAL NOT NULL DEFAULT 0.0,
                created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            # Monthly usage summaries
            """
            CREATE TABLE IF NOT EXISTS usage_summaries (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                personality_id  TEXT NOT NULL,
                year_month      TEXT NOT NULL,
                total_tokens    INTEGER NOT NULL DEFAULT 0,
                total_cost      REAL NOT NULL DEFAULT 0.0,
                UNIQUE(personality_id, year_month)
            )
            """,
        ]
        for sql in migrations:
            await self.conn.execute(sql)
        await self.conn.commit()
