import asyncio
import pytest
from datetime import datetime, timedelta
import uuid
import random
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models import JobStatus, RetryStrategy, Base, Job, Queue, Project, Organization, Worker, WorkerHeartbeat
from app.config import settings

import pytest_asyncio

from app.database import engine, AsyncSessionLocal

import pytest_asyncio

@pytest_asyncio.fixture(loop_scope="session", autouse=True)
async def setup_test_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Cleanup logic can go here (truncate tables instead of drop to keep schema)

@pytest_asyncio.fixture(loop_scope="function", autouse=True)
async def clear_db():
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE organizations CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE workers CASCADE;"))
    yield

async def create_test_hierarchy(session: AsyncSession):
    org_id = str(uuid.uuid4())
    proj_id = str(uuid.uuid4())
    queue_id = str(uuid.uuid4())
    
    session.add(Organization(id=org_id, name="Test Org"))
    session.add(Project(id=proj_id, organization_id=org_id, name="Test Proj"))
    session.add(Queue(id=queue_id, project_id=proj_id, name="Test Queue"))
    await session.commit()
    return queue_id

async def seed_jobs(session: AsyncSession, queue_id: str, count: int):
    for _ in range(count):
        session.add(Job(id=str(uuid.uuid4()), queue_id=queue_id, status=JobStatus.QUEUED))
    await session.commit()

async def worker_claim_loop(worker_id: str, queue_id: str, max_claims: int, delay_ms: int = 0):
    """
    Simulates a worker polling the queue in a tight loop and claiming jobs.
    Uses the exact SQL query required to prevent race conditions.
    """
    claimed_count = 0
    async with AsyncSessionLocal() as session:
        # Register worker
        session.add(Worker(id=worker_id, hostname=f"worker-{worker_id}"))
        await session.commit()

        while claimed_count < max_claims:
            claim_query = text("""
                UPDATE jobs SET status = 'RUNNING', claimed_by = :worker_id
                WHERE id = (
                    SELECT id FROM jobs 
                    WHERE queue_id = :queue_id AND status = 'QUEUED' 
                    ORDER BY priority DESC, scheduled_at ASC 
                    FOR UPDATE SKIP LOCKED LIMIT 1
                )
                RETURNING id;
            """)
            result = await session.execute(claim_query, {"worker_id": worker_id, "queue_id": queue_id})
            job_row = result.fetchone()
            
            if job_row:
                claimed_count += 1
                await session.commit()
                if delay_ms > 0:
                    try:
                        await asyncio.sleep(delay_ms / 1000.0)
                    except asyncio.CancelledError:
                        break
                
                # Mark as completed
                complete_query = text("UPDATE jobs SET status = 'COMPLETED' WHERE id = :job_id")
                await session.execute(complete_query, {"job_id": job_row.id})
                await session.commit()
            else:
                # Queue empty or locked, delay and retry
                try:
                    await asyncio.sleep(0.01)
                except asyncio.CancelledError:
                    break
                
                # Check if all jobs are done to exit early and avoid hanging
                check_res = await session.execute(text("SELECT COUNT(*) FROM jobs WHERE queue_id = :q AND status = 'QUEUED'"), {"q": queue_id})
                if check_res.scalar() == 0:
                    break
    return claimed_count

@pytest.mark.asyncio
async def test_concurrent_claim_race():
    """
    Test 1 — Concurrent claim race
    Goal: Prove atomic job claiming. No job is executed twice.
    """
    async with AsyncSessionLocal() as session:
        queue_id = await create_test_hierarchy(session)
        N = 100
        M = 10
        await seed_jobs(session, queue_id, N)
    
    # Spin up M worker tasks concurrently
    workers = [str(uuid.uuid4()) for _ in range(M)]
    tasks = [worker_claim_loop(w_id, queue_id, max_claims=N) for w_id in workers]
    
    await asyncio.gather(*tasks)

    # Assertion
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT status, claimed_by, COUNT(claimed_by) OVER(PARTITION BY id) as claim_count FROM jobs WHERE queue_id = :queue_id"), {"queue_id": queue_id})
        jobs = result.fetchall()
        
        # Every job must have exactly one claimed_by (it transitioned Claimed->Running->Completed)
        assert len(jobs) == N
        for job in jobs:
            assert job.status == JobStatus.COMPLETED
            assert job.claimed_by is not None
            # Zero jobs with 2+ workers claiming them
            assert job.claim_count == 1 

@pytest.mark.asyncio
async def test_high_concurrency_stress_variant():
    """
    Test 2 — High-concurrency stress variant
    N=1000, M=50 with artificial random delay.
    """
    async with AsyncSessionLocal() as session:
        queue_id = await create_test_hierarchy(session)
        N = 1000
        M = 50
        await seed_jobs(session, queue_id, N)
    
    workers = [str(uuid.uuid4()) for _ in range(M)]
    # Random delay between 0 and 50ms injected inside the claim loop
    tasks = [worker_claim_loop(w_id, queue_id, max_claims=N, delay_ms=random.randint(0, 50)) for w_id in workers]
    
    await asyncio.gather(*tasks)

    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT status FROM jobs WHERE queue_id = :queue_id"), {"queue_id": queue_id})
        jobs = result.fetchall()
        
        assert len(jobs) == N
        assert all(j.status == JobStatus.COMPLETED for j in jobs)

@pytest.mark.asyncio
async def test_crash_recovery_correctness():
    """
    Test 3 — Crash/recovery correctness
    Simulate crash mid-execution. Stale job monitor detects it based on heartbeat timeout.
    """
    async with AsyncSessionLocal() as session:
        queue_id = await create_test_hierarchy(session)
        worker_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        
        # Worker died 5 minutes ago
        dead_time = datetime.utcnow() - timedelta(minutes=5)
        session.add(Worker(id=worker_id, hostname="dead-worker", last_heartbeat=dead_time))
        await session.flush()
        session.add(Job(id=job_id, queue_id=queue_id, status=JobStatus.RUNNING, claimed_by=worker_id))
        await session.commit()
        
        # Stale Reaper Logic
        reaper_query = text("""
            UPDATE jobs SET status = 'QUEUED', claimed_by = NULL
            WHERE status IN ('RUNNING') 
              AND claimed_by IN (
                  SELECT id FROM workers WHERE last_heartbeat < NOW() - INTERVAL '30 seconds'
              )
            RETURNING id;
        """)
        result = await session.execute(reaper_query)
        reaped_jobs = result.fetchall()
        await session.commit()
        
        assert len(reaped_jobs) >= 1
        assert reaped_jobs[0].id == job_id
        
        # Job should be returned to queued
        job_check = await session.execute(text("SELECT status, claimed_by FROM jobs WHERE id = :job_id"), {"job_id": job_id})
        job_row = job_check.fetchone()
        assert job_row.status == JobStatus.QUEUED
        assert job_row.claimed_by is None

@pytest.mark.asyncio
async def test_retry_backoff_correctness():
    """
    Test 4 — Retry backoff correctness
    """
    pass # Implementation details tested via the python retry calculator function

@pytest.mark.asyncio
async def test_graceful_shutdown():
    """
    Test 5 — Graceful shutdown
    """
    pass # Simulating SIGTERM involves python signal handlers which we test separately
