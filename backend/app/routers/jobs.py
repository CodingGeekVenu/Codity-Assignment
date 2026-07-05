from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import uuid
from typing import List, Optional

from app.database import get_db
from app.models import Job, Queue, JobStatus, ScheduledJob
from app.schemas import JobCreate, JobResponse, JobStatusResponse, BatchJobCreate, ScheduledJobCreate, ScheduledJobResponse, JobLogResponse

from app.routers.auth import get_current_user

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(job: JobCreate, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_user)):
    queue_query = await db.execute(select(Queue).where(Queue.id == job.queue_id))
    if not queue_query.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Queue not found")
        
    new_job = Job(
        id=str(uuid.uuid4()),
        queue_id=job.queue_id,
        priority=job.priority,
        payload=job.payload,
        status=JobStatus.SCHEDULED if job.scheduled_at else JobStatus.QUEUED,
        scheduled_at=job.scheduled_at
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)
    return new_job

@router.post("/batch", response_model=List[JobResponse], status_code=status.HTTP_201_CREATED)
async def create_batch_jobs(batch: BatchJobCreate, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_user)):
    if not batch.jobs:
        return []
    
    # Assume all jobs in batch are for the same queue for validation (or check individually)
    queue_ids = {j.queue_id for j in batch.jobs}
    queues_query = await db.execute(select(Queue).where(Queue.id.in_(queue_ids)))
    valid_queues = {q.id for q in queues_query.scalars().all()}
    
    if len(valid_queues) != len(queue_ids):
        raise HTTPException(status_code=400, detail="One or more queues not found")
        
    new_jobs = []
    for job_in in batch.jobs:
        new_job = Job(
            id=str(uuid.uuid4()),
            queue_id=job_in.queue_id,
            priority=job_in.priority,
            payload=job_in.payload,
            status=JobStatus.SCHEDULED if job_in.scheduled_at else JobStatus.QUEUED,
            scheduled_at=job_in.scheduled_at
        )
        new_jobs.append(new_job)
        
    db.add_all(new_jobs)
    await db.commit()
    
    for job in new_jobs:
        await db.refresh(job)
        
    return new_jobs

@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job_query = await db.execute(select(Job).where(Job.id == job_id))
    job = job_query.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return job

@router.get("/dlq/all", response_model=List[dict])
async def get_dlq(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    result = await db.execute(text("SELECT id, job_id, queue_id, payload, error_summary, ai_failure_summary, failed_at FROM dead_letter_queue ORDER BY failed_at DESC LIMIT 50"))
    rows = result.fetchall()
    return [
        {
            "id": r.id,
            "job_id": r.job_id,
            "queue_id": r.queue_id,
            "payload": r.payload,
            "error_summary": r.error_summary,
            "ai_failure_summary": r.ai_failure_summary,
            "failed_at": r.failed_at.isoformat() if r.failed_at else None
        } for r in rows
    ]

@router.post("/scheduled", response_model=ScheduledJobResponse, status_code=status.HTTP_201_CREATED)
async def create_scheduled_job(job: ScheduledJobCreate, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_user)):
    import croniter
    if not croniter.croniter.is_valid(job.cron_expression):
        raise HTTPException(status_code=400, detail="Invalid cron expression")
        
    queue_query = await db.execute(select(Queue).where(Queue.id == job.queue_id))
    if not queue_query.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Queue not found")
        
    new_job = ScheduledJob(
        id=str(uuid.uuid4()),
        queue_id=job.queue_id,
        cron_expression=job.cron_expression,
        payload=job.payload
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)
    return new_job

@router.get("/queue/{queue_id}", response_model=List[JobResponse])
async def get_jobs_for_queue(queue_id: str, skip: int = 0, limit: int = 20, status_filter: Optional[JobStatus] = None, db: AsyncSession = Depends(get_db)):
    query = select(Job).where(Job.queue_id == queue_id)
    if status_filter:
        query = query.where(Job.status == status_filter)
        
    query = query.order_by(Job.created_at.desc()).offset(skip).limit(limit)
    job_query = await db.execute(query)
    return job_query.scalars().all()

@router.get("/{job_id}/logs", response_model=List[JobLogResponse])
async def get_job_logs(job_id: str, db: AsyncSession = Depends(get_db)):
    from app.models import JobLog
    query = select(JobLog).where(JobLog.job_id == job_id).order_by(JobLog.created_at.asc())
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(job_id: str, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_user)):
    from sqlalchemy import text
    # Fetch job to verify it's FAILED or in DLQ
    job_query = await db.execute(select(Job).where(Job.id == job_id))
    job = job_query.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job.status != JobStatus.FAILED:
        raise HTTPException(status_code=400, detail="Only FAILED jobs can be retried manually")
        
    # Reset job
    job.status = JobStatus.QUEUED
    job.attempts = 0
    job.scheduled_at = None
    job.claimed_by = None
    
    # Remove from DLQ if it was there
    await db.execute(text("DELETE FROM dead_letter_queue WHERE job_id = :jid"), {"jid": job_id})
    
    await db.commit()
    await db.refresh(job)
    return job
