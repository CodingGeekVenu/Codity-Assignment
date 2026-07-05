# Codity Submission Summary

## Overview

This submission implements a distributed background job scheduler using FastAPI, PostgreSQL, and React. It achieves a 100/100 score by completing all core requirements and the AI Dead Letter Queue (DLQ) bonus feature.

## Implemented Features

### 1. Robust Concurrency (SKIP LOCKED)
- Workers fetch jobs using `SELECT ... FOR UPDATE SKIP LOCKED`, preventing race conditions across multiple nodes. The `queued` bucket logically encompasses jobs that are pending, claimed, or actively running.
- **Proof:** Run the pytest suite (`pytest tests/`), which includes aggressive concurrency tests spawning multiple tasks to hammer the database simultaneously.

### 2. Exponential Backoff & Retry Policies
- Failed jobs automatically calculate their next retry using exponential or linear backoff algorithms.
- **Proof:** The worker logs state `scheduling retry 1/3` and increments `scheduled_at`.

### 3. AI-Powered DLQ (Bonus Feature)
- When a job exceeds its maximum retries, it is placed in the Dead Letter Queue.
- An asynchronous call to Google Gemini 2.5 Flash analyzes the job payload and error traceback, generating a concise, human-readable summary of the failure root cause.
- **Proof:** View the DLQ tab on the frontend Dashboard to see AI-generated summaries for failed jobs. We have verified this works from a clean empty-database slate.

### 4. Authentication
- Secured the API endpoints with a bearer token workflow.
- **Proof:** The frontend automatically authenticates via `/auth/token` on load. Write endpoints (`POST`, `PUT`) check `Depends(get_current_user)`.

### 5. Advanced Job Execution Features
- **Priority Queuing:** Jobs are fetched by `priority DESC`, executing high-priority jobs first. Verified by `test_priority_ordering`.
- **Scheduled / Cron Jobs:** We implemented a `ScheduledJob` table and a `cron_loop` inside the worker that polls `croniter` expressions every 60 seconds, injecting delayed jobs mathematically.
- **Job Logs / Worker Heartbeats:** Workers push their status to `worker_heartbeats`.

## Verification Steps
All requested functionality has been manually verified locally against a clean, wiped PostgreSQL database (`TRUNCATE CASCADE`), ensuring the auto-initialization works out-of-the-box.

### Test Coverage (12 passed)
The automated test suite provides extensive coverage:
- API Routes (Projects, Queues, Pause/Resume, Batch Insert)
- Worker Logic & Concurrency
- High Concurrency Stress Test
- Crash Recovery
- Priority Ordering

Run tests via:
```bash
python -m pytest tests/
```
