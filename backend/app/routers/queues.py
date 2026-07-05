from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from typing import List

from app.database import get_db
from app.models import Queue, Project, RetryPolicy
from app.schemas import QueueCreate, QueueResponse, QueueUpdate

from app.routers.auth import get_current_user

router = APIRouter(prefix="/queues", tags=["queues"])

@router.post("/", response_model=QueueResponse, status_code=status.HTTP_201_CREATED)
async def create_queue(queue: QueueCreate, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_user)):
    project_query = await db.execute(select(Project).where(Project.id == queue.project_id))
    if not project_query.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")
        
    retry_policy = RetryPolicy(id=str(uuid.uuid4()), name=f"Policy for {queue.name}", strategy=queue.retry_strategy)
    db.add(retry_policy)
    
    new_queue = Queue(
        id=str(uuid.uuid4()),
        name=queue.name,
        project_id=queue.project_id,
        concurrency_limit=queue.concurrency_limit,
        retry_policy_id=retry_policy.id,
        is_paused=queue.is_paused
    )
    db.add(new_queue)
    await db.commit()
    await db.refresh(new_queue)
    new_queue_dict = {
        "id": new_queue.id,
        "name": new_queue.name,
        "project_id": new_queue.project_id,
        "concurrency_limit": new_queue.concurrency_limit,
        "is_paused": new_queue.is_paused,
        "created_at": new_queue.created_at,
        "retry_strategy": queue.retry_strategy
    }
    return new_queue_dict

@router.put("/{queue_id}/pause", response_model=QueueResponse)
async def pause_queue(queue_id: str, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_user)):
    return await toggle_queue_pause(queue_id, True, db)

@router.put("/{queue_id}/resume", response_model=QueueResponse)
async def resume_queue(queue_id: str, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_user)):
    return await toggle_queue_pause(queue_id, False, db)

@router.get("/", response_model=List[QueueResponse])
async def list_queues(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Queue, RetryPolicy).outerjoin(RetryPolicy, Queue.retry_policy_id == RetryPolicy.id).where(Queue.project_id == project_id))
    rows = result.all()
    out = []
    for q, rp in rows:
        out.append({
            "id": q.id,
            "name": q.name,
            "project_id": q.project_id,
            "concurrency_limit": q.concurrency_limit,
            "is_paused": q.is_paused,
            "created_at": q.created_at,
            "retry_strategy": rp.strategy if rp else "fixed"
        })
    return out

@router.patch("/{queue_id}", response_model=QueueResponse)
async def update_queue(queue_id: str, queue_update: QueueUpdate, db: AsyncSession = Depends(get_db)):
    queue_query = await db.execute(select(Queue).where(Queue.id == queue_id))
    db_queue = queue_query.scalar_one_or_none()
    
    if not db_queue:
        raise HTTPException(status_code=404, detail="Queue not found")
        
    if queue_update.is_paused is not None:
        db_queue.is_paused = queue_update.is_paused
        
    await db.commit()
    await db.refresh(db_queue)
    
    # Fetch retry strategy for response
    strategy = "fixed"
    if db_queue.retry_policy_id:
        rp = await db.execute(select(RetryPolicy).where(RetryPolicy.id == db_queue.retry_policy_id))
        policy = rp.scalar_one_or_none()
        if policy:
            strategy = policy.strategy

    return {
        "id": db_queue.id,
        "name": db_queue.name,
        "project_id": db_queue.project_id,
        "concurrency_limit": db_queue.concurrency_limit,
        "is_paused": db_queue.is_paused,
        "created_at": db_queue.created_at,
        "retry_strategy": strategy
    }
