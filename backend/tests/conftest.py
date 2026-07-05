import pytest
import pytest_asyncio
from sqlalchemy import text
from app.database import engine, Base
from app.main import app
from app.routers.auth import get_current_user

@pytest_asyncio.fixture(loop_scope="session", autouse=True)
async def setup_test_db():
    app.dependency_overrides[get_current_user] = lambda: "testuser"
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    app.dependency_overrides.clear()
