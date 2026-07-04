from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import jobs, queues, projects, auth

app = FastAPI(
    title="Distributed Job Scheduler API",
    description="API for managing projects, queues, jobs, and monitoring workers.",
    version="1.0.0"
)

# CORS middleware for the dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(queues.router)
app.include_router(jobs.router)

@app.get("/")
async def root():
    return {"message": "Welcome to the Distributed Job Scheduler API", "status": "operational"}
