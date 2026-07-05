import asyncio
from app.database import engine, Base
from app import models

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("DB initialized!")

if __name__ == "__main__":
    asyncio.run(init_db())
