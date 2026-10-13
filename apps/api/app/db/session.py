from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings) -> AsyncEngine:
    global _engine
    if _engine is None:
        kwargs: dict = {"pool_pre_ping": True}
        if settings.app_env != "production":
            kwargs["poolclass"] = NullPool
        _engine = create_async_engine(settings.database_url, **kwargs)
    return _engine


def get_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(settings), expire_on_commit=False)
    return _session_factory


async def check_database(settings: Settings) -> bool:
    engine = get_engine(settings)
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return True


async def get_db() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory(get_settings())
    async with factory() as session:
        yield session


@asynccontextmanager
async def engine_lifespan(settings: Settings) -> AsyncIterator[None]:
    get_engine(settings)
    try:
        yield
    finally:
        global _engine, _session_factory
        if _engine is not None:
            await _engine.dispose()
            _engine = None
            _session_factory = None
