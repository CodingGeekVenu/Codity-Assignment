from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models import Worker
from app.schemas import WorkerResponse

router = APIRouter(prefix="/workers", tags=["workers"])

@router.get("/", response_model=List[WorkerResponse])
async def list_workers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Worker).order_by(Worker.last_heartbeat.desc()))
    return result.scalars().all()
