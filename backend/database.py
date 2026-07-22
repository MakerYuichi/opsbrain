"""
database.py — SQLAlchemy setup with Base definition.

NOTE: This codebase uses synchronous database access as the standard pattern.
The async functions below are retained for potential future use but are not
currently used in the main application flow.

Standard Pattern:
- Use SyncSession from fact_builder.py for all database operations
- Routers, agents, and ingestion all use sync sessions for consistency
- Async complexity not justified for current workload scale

Rationale for Sync Standard:
- Simpler error handling in FastAPI routes
- Easier debugging and testing
- Sufficient performance for current workload (~300 facts)
- Consistent pattern across ingestion, agents, and routers
- Consider async only if performance becomes bottleneck
"""
import os
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# ── Async engine — only constructed when actually needed by FastAPI ────────────

def get_async_engine():
    from sqlalchemy.ext.asyncio import create_async_engine
    url = os.getenv("DATABASE_URL", "sqlite:///./industrial_ki.db")
    # Ensure async driver prefix
    if url.startswith("sqlite:///") and "+aiosqlite" not in url:
        url = url.replace("sqlite:///", "sqlite+aiosqlite:///")
    return create_async_engine(url, echo=False)


def get_async_session_factory():
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    return sessionmaker(get_async_engine(), class_=AsyncSession,
                        expire_on_commit=False)


async def get_db():
    factory = get_async_session_factory()
    async with factory() as session:
        yield session


async def init_db():
    engine = get_async_engine()
    async with engine.begin() as conn:
        from models import Base as _Base
        await conn.run_sync(_Base.metadata.create_all)
