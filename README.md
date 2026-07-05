# Distributed Job Scheduler (Codity Assignment)

This repository contains the backend and frontend for the Distributed Job Scheduler assignment.

## Tech Stack
- **Backend:** Python 3.10+, FastAPI, PostgreSQL, SQLAlchemy (asyncpg), Google Gemini AI SDK.
- **Frontend:** React 19, Vite, TypeScript, Tailwind CSS, Shadcn UI.

## Features Implemented
1. **Concurrency and Scaling:** Designed with `SELECT ... FOR UPDATE SKIP LOCKED` in PostgreSQL for atomic job locking, allowing multiple concurrent workers without overlapping executions or deadlocks.
2. **Reliability & Retry Strategy:** Built-in backoff mechanisms for `FIXED`, `LINEAR`, and `EXPONENTIAL` retry strategies natively integrated into the queue definitions.
3. **Dead Letter Queue (DLQ):** Failed jobs after max retries enter the DLQ permanently. Features a fully functional 1-click **Retry** button in the dashboard that restores them to the active queues.
4. **AI Failure Analysis:** We integrated Google Gemini AI 2.5 Flash to automatically analyze failure payloads in the DLQ and generate natural-language root-cause analyses on failure payloads.
5. **Worker Heartbeats:** Live tracking of all background workers processing jobs, with active status polling.
6. **Execution Logs:** The system natively captures and surfaces complete execution logs of every job attempt and failure stack trace.
7. **Modern Dashboard:** React-based dashboard polling the API every 3s to reflect live job queues, queue toggling (pause/resume), worker heartbeat tracking, logs terminal, and a detailed DLQ viewer.

## Project Structure
- `/backend`: The FastAPI application, API routers, database schemas, migration tools, background worker scripts, and rigorous pytest suite.
- `/frontend`: The Vite+React TSX application.
- `/docs`: Contains the final `Codity_Submission.md` covering architecture, scheme, and feature design details.

## Getting Started

### 1. Database Setup
Create a local PostgreSQL database, then initialize it:
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
set DATABASE_URL=postgresql+asyncpg://jobuser:jobpassword@localhost:5432/job_scheduler
set SYNC_DATABASE_URL=postgresql://jobuser:jobpassword@localhost:5432/job_scheduler
python init_db.py
```

### 2. Start the Backend API
```bash
uvicorn app.main:app --reload
```

### 3. Start the Background Worker
In a new terminal:
```bash
cd backend
.\venv\Scripts\activate
set DATABASE_URL=postgresql+asyncpg://jobuser:jobpassword@localhost:5432/job_scheduler
set GEMINI_API_KEY=your_key_here
python -m app.worker
```

### 4. Start the Frontend Dashboard
In a new terminal:
```bash
cd frontend
npm install
npm run dev
```

### 5. Running the Automated Tests
The `pytest` suite tests authentication, queue creation, job processing, and strictly tests concurrency against 50 parallel workers fighting for jobs.
```bash
cd backend
python -m pytest tests/
```

To see the system run live, start the backend and worker, then run:
```bash
python test_workflow.py
```
