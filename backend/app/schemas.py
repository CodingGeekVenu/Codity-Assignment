from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.models import JobStatus, RetryStrategy

class ProjectCreate(BaseModel):
    name: str = Field(..., example="Email Campaign")
    organization_id: str

class ProjectResponse(ProjectCreate):
    id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class QueueCreate(BaseModel):
    name: str = Field(..., example="default")
    project_id: str
    concurrency_limit: int = 10
    retry_strategy: RetryStrategy = RetryStrategy.FIXED
    is_paused: bool = False

class QueueResponse(QueueCreate):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

class QueueUpdate(BaseModel):
    is_paused: Optional[bool] = None

class JobCreate(BaseModel):
    queue_id: str
    priority: int = 0
    payload: Dict[str, Any] = Field(default_factory=dict)
    scheduled_at: Optional[datetime] = None

class JobResponse(JobCreate):
    id: str
    status: JobStatus
    attempts: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class JobStatusResponse(BaseModel):
    id: str
    status: JobStatus
    attempts: int
    error_summary: Optional[str] = None
    ai_failure_summary: Optional[str] = None

class BatchJobCreate(BaseModel):
    jobs: List[JobCreate]
