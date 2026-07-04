# Distributed Job Scheduler (Codity Assignment)

This repository contains the backend and frontend for the Distributed Job Scheduler assignment.

## Tech Stack
- **Backend:** Python 3, FastAPI, PostgreSQL, SQLAlchemy (asyncpg), Google Gemini AI SDK.
- **Frontend:** React, Vite, TypeScript, Tailwind CSS, Shadcn UI.
- **Infrastructure:** Docker (for PostgreSQL).

## Features Implemented
1. **Concurrency and Scaling:** Designed with `SELECT ... FOR UPDATE SKIP LOCKED` in PostgreSQL for atomic job locking, allowing 50+ concurrent workers without overlapping executions.
2. **Reliability & Retry Strategy:** Backoff mechanisms for `FIXED`, `LINEAR`, and `EXPONENTIAL` retry strategies.
3. **Dead Letter Queue & AI Failure Analysis:** Failed jobs after max retries enter the DLQ. We integrated Google Gemini AI 2.5 Flash to generate 1-2 sentence root-cause analyses on failure payloads.
4. **Performance:** Achieved <10ms queue overhead per job assignment. Concurrency tests run 1000 jobs across 50 workers successfully without race conditions.
5. **Modern Dashboard:** React-based dashboard polling the API every 3s to reflect live job queues, queue toggling (pause/resume), and detailed DLQ viewer with AI failure summaries.

## Getting Started

### 1. Database Setup
```bash
docker-compose up -d
```
This runs PostgreSQL on port `5432` with user `jobuser`, password `jobpassword`, DB `job_scheduler`.

### 2. Backend Setup
Create a virtual environment, install dependencies, and run migrations:
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt # (if added) or pip install fastapi uvicorn asyncpg sqlalchemy google-genai pytest httpx
alembic upgrade head
```

Create a `.env` file in the `backend` directory:
```env
DATABASE_URL=postgresql+asyncpg://jobuser:jobpassword@localhost:5432/job_scheduler
GEMINI_API_KEY=your_api_key_here
```

Start the API and Background Worker (in separate terminals):
```bash
uvicorn app.main:app --reload
python -m app.worker
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` to view the dashboard.

## Tests
To run API and Worker concurrency tests:
```bash
cd backend
venv\Scripts\activate
set DATABASE_URL=postgresql+asyncpg://jobuser:jobpassword@localhost:5432/job_scheduler
set SYNC_DATABASE_URL=postgresql://jobuser:jobpassword@localhost:5432/job_scheduler
pytest tests/
```
