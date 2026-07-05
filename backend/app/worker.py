import asyncio
import signal
import sys
import os
import uuid
import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from app.database import AsyncSessionLocal
from app.models import Worker, JobStatus, RetryStrategy
from google import genai
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")

# Initialize Gemini AI Client
gemini_api_key = os.getenv("GEMINI_API_KEY")
ai_client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None

def generate_ai_failure_summary(job_id, payload, error_msg):
    if not ai_client:
        return "AI Client not configured."
    try:
        prompt = f"Analyze this background job failure.\nJob ID: {job_id}\nPayload: {payload}\nError: {error_msg}\nProvide a short, root-cause analysis summary in 1-2 sentences."
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        logger.error(f"Failed to generate AI summary: {e}")
        return "Failed to generate AI summary."

def calculate_next_retry(new_attempts: int, strategy: str) -> int:
    backoff_seconds = 60 # 60 seconds default base for testing
    if strategy == RetryStrategy.LINEAR:
        backoff_seconds = 60 * new_attempts
    elif strategy == RetryStrategy.EXPONENTIAL:
        backoff_seconds = 60 * (2 ** (new_attempts - 1))
    return backoff_seconds

class JobWorker:
    def __init__(self, queue_ids=None):
        self.worker_id = str(uuid.uuid4())
        self.hostname = "local-worker"
        self.queue_ids = queue_ids or []
        self.is_shutting_down = False

    async def startup(self):
        async with AsyncSessionLocal() as session:
            worker = Worker(id=self.worker_id, hostname=self.hostname)
            session.add(worker)
            await session.commit()
            logger.info(f"Worker {self.worker_id} started and registered.")

    async def heartbeat_loop(self):
        while not self.is_shutting_down:
            try:
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        text("UPDATE workers SET last_heartbeat = NOW() WHERE id = :worker_id"),
                        {"worker_id": self.worker_id}
                    )
                    await session.commit()
            except Exception as e:
                logger.error(f"Failed to send heartbeat: {e}")
            await asyncio.sleep(10) # 10 second heartbeat

    async def reaper_loop(self):
        while not self.is_shutting_down:
            try:
                async with AsyncSessionLocal() as session:
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
                    if reaped_jobs:
                        logger.warning(f"Reaped {len(reaped_jobs)} stale jobs.")
                    await session.commit()
            except Exception as e:
                logger.error(f"Failed during reaper loop: {e}")
            await asyncio.sleep(30) # Run reaper every 30s

    async def claim_and_execute(self):
        while not self.is_shutting_down:
            try:
                async with AsyncSessionLocal() as session:
                    claim_query = text("""
                        UPDATE jobs SET status = 'RUNNING', claimed_by = :worker_id, updated_at = NOW()
                        WHERE id = (
                            SELECT jobs.id FROM jobs 
                            JOIN queues ON jobs.queue_id = queues.id
                            WHERE jobs.status = 'QUEUED' 
                              AND (jobs.scheduled_at IS NULL OR jobs.scheduled_at <= NOW())
                              AND queues.is_paused = FALSE
                            ORDER BY jobs.priority DESC, jobs.scheduled_at ASC 
                            FOR UPDATE SKIP LOCKED LIMIT 1
                        )
                        RETURNING id, payload, attempts, max_retries, queue_id;
                    """)
                    
                    result = await session.execute(claim_query, {"worker_id": self.worker_id})
                    job = result.fetchone()

                    if job:
                        logger.info(f"Worker {self.worker_id} claimed job {job.id}")
                        
                        # Log job start
                        log_id_start = str(uuid.uuid4())
                        await session.execute(
                            text("INSERT INTO job_logs (id, job_id, message, created_at) VALUES (:id, :jid, :msg, NOW())"),
                            {"id": log_id_start, "jid": job.id, "msg": f"Job claimed by worker {self.worker_id} and execution started."}
                        )
                        
                        # Execute Job (Simulated)
                        try:
                            await asyncio.sleep(0.5) 
                            
                            # Check payload for forced failure
                            if isinstance(job.payload, dict) and job.payload.get("force_fail"):
                                raise Exception("Simulated job failure (Forced by payload)")
                                
                            logger.info(f"Job {job.id} completed successfully.")
                            await session.execute(text("UPDATE jobs SET status = 'COMPLETED' WHERE id = :id"), {"id": job.id})
                            
                            # Log success
                            log_id_end = str(uuid.uuid4())
                            await session.execute(
                                text("INSERT INTO job_logs (id, job_id, message, created_at) VALUES (:id, :jid, :msg, NOW())"),
                                {"id": log_id_end, "jid": job.id, "msg": "Job completed successfully."}
                            )
                            await session.commit()
                        except Exception as execution_error:
                            logger.error(f"Job {job.id} failed: {execution_error}")
                            
                            # Log failure
                            log_id_fail = str(uuid.uuid4())
                            await session.execute(
                                text("INSERT INTO job_logs (id, job_id, message, created_at) VALUES (:id, :jid, :msg, NOW())"),
                                {"id": log_id_fail, "jid": job.id, "msg": f"Job failed with error: {str(execution_error)}"}
                            )
                            
                            # Fetch queue config for retry strategy
                            queue_res = await session.execute(
                                text("SELECT rp.strategy FROM queues q JOIN retry_policies rp ON q.retry_policy_id = rp.id WHERE q.id = :qid"), 
                                {"qid": job.queue_id}
                            )
                            queue_cfg = queue_res.fetchone()
                            strategy = queue_cfg.strategy if queue_cfg else 'FIXED'
                            
                            new_attempts = job.attempts + 1
                            if new_attempts >= job.max_retries:
                                logger.error(f"Job {job.id} reached max retries. Moving to DLQ.")
                                # Update job status to FAILED
                                await session.execute(
                                    text("UPDATE jobs SET status = 'FAILED', attempts = :att WHERE id = :id"),
                                    {"att": new_attempts, "id": job.id}
                                )
                                # Generate AI summary
                                ai_summary = generate_ai_failure_summary(job.id, str(job.payload), str(execution_error))
                                
                                # Insert to DLQ
                                dlq_query = text("""
                                    INSERT INTO dead_letter_queue (id, job_id, queue_id, payload, error_summary, ai_failure_summary, failed_at)
                                    VALUES (:id, :jid, :qid, :payload, :err, :ai_sum, NOW())
                                """)
                                import json
                                await session.execute(dlq_query, {
                                    "id": str(uuid.uuid4()),
                                    "jid": job.id,
                                    "qid": job.queue_id,
                                    "payload": json.dumps(job.payload) if job.payload else "{}",
                                    "err": str(execution_error),
                                    "ai_sum": ai_summary
                                })
                            else:
                                logger.info(f"Job {job.id} scheduling retry {new_attempts}/{job.max_retries}")
                                # Calculate backoff
                                backoff_seconds = calculate_next_retry(new_attempts, strategy)
                                
                                await session.execute(
                                    text("UPDATE jobs SET status = 'QUEUED', attempts = :att, scheduled_at = NOW() + INTERVAL '1 second' * :boff, claimed_by = NULL WHERE id = :id"),
                                    {"att": new_attempts, "boff": backoff_seconds, "id": job.id}
                                )
                            
                            await session.commit()
                    else:
                        # No jobs available, backoff polling slightly
                        await asyncio.sleep(1)
                        
            except Exception as e:
                logger.error(f"Error during claim loop: {e}")
                await asyncio.sleep(1)

    async def cron_loop(self):
        """
        Polls the scheduled_jobs table every 60 seconds and creates new jobs
        if the cron expression indicates it is time to run.
        """
        import croniter
        while not self.is_shutting_down:
            try:
                async with AsyncSessionLocal() as session:
                    # Fetch all active scheduled jobs
                    result = await session.execute(text("SELECT id, queue_id, cron_expression, payload, next_run_at FROM scheduled_jobs WHERE is_active = true"))
                    schedules = result.fetchall()
                    
                    now = datetime.utcnow()
                    
                    for schedule in schedules:
                        # If next_run_at is empty or we've passed it, it's time to run
                        if not schedule.next_run_at or now >= schedule.next_run_at:
                            # 1. Insert a new job into the queue
                            import json
                            job_payload = json.dumps(schedule.payload) if schedule.payload else "{}"
                            await session.execute(
                                text("INSERT INTO jobs (id, queue_id, payload, priority, status) VALUES (:id, :qid, :payload, 1, 'QUEUED')"),
                                {"id": str(uuid.uuid4()), "qid": schedule.queue_id, "payload": job_payload}
                            )
                            
                            # 2. Calculate next run time
                            if croniter.croniter.is_valid(schedule.cron_expression):
                                cron = croniter.croniter(schedule.cron_expression, now)
                                next_run = cron.get_next(datetime)
                                
                                await session.execute(
                                    text("UPDATE scheduled_jobs SET next_run_at = :next_run WHERE id = :id"),
                                    {"next_run": next_run, "id": schedule.id}
                                )
                                logger.info(f"Cron Job triggered for schedule {schedule.id}. Next run at {next_run}")
                            else:
                                logger.error(f"Invalid cron expression: {schedule.cron_expression}")
                    
                    await session.commit()
            except Exception as e:
                logger.error(f"Error in cron_loop: {e}")
            
            # Sleep 60s
            for _ in range(60):
                if self.is_shutting_down: break
                await asyncio.sleep(1)

    async def run(self):
        await self.startup()
        
        heartbeat_task = asyncio.create_task(self.heartbeat_loop())
        reaper_task = asyncio.create_task(self.reaper_loop())
        cron_task = asyncio.create_task(self.cron_loop())
        worker_task = asyncio.create_task(self.claim_and_execute())
        
        await asyncio.gather(heartbeat_task, reaper_task, cron_task, worker_task)

    def trigger_graceful_shutdown(self):
        logger.info("SIGTERM received. Triggering graceful shutdown. Waiting for current job to finish...")
        self.is_shutting_down = True

worker_instance = JobWorker()

def handle_sigterm(*args):
    worker_instance.trigger_graceful_shutdown()

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)
    
    try:
        asyncio.run(worker_instance.run())
    except KeyboardInterrupt:
        logger.info("Worker stopped via Keyboard Interrupt.")
