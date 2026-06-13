"""Hermes Personalities UI — FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.database import Database

settings = Settings()
db = Database()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, load config, seed demo data if empty."""
    data_dir = Path(settings.data_path)
    data_dir.mkdir(parents=True, exist_ok=True)

    await db.connect(settings.data_path / "personalities.db")
    await db.run_migrations()

    from app.services.migration import MigrationService
    migration = MigrationService(data_dir)
    await migration.seed_demo_if_empty(db)

    yield

    await db.close()


app = FastAPI(
    title="Hermes Personalities UI",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# Import routers after app creation to avoid circular imports
from app.routers import personalities  # noqa: E402
from app.routers import sessions       # noqa: E402
from app.routers import providers      # noqa: E402
from app.routers import mcp            # noqa: E402
from app.routers import cron           # noqa: E402
from app.routers import workflows      # noqa: E402
from app.routers import usage          # noqa: E402

app.include_router(personalities.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(providers.router, prefix="/api", tags=["providers"])
app.include_router(mcp.router, prefix="/api", tags=["mcp"])
app.include_router(cron.router, prefix="/api", tags=["cron"])
app.include_router(workflows.router, prefix="/api", tags=["workflows"])
app.include_router(usage.router, prefix="/api", tags=["usage"])
