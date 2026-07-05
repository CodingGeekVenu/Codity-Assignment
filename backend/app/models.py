import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, Text, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum

from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    SCHEDULED = "SCHEDULED"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class RetryStrategy(str, enum.Enum):
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"

class Organization(Base):
    __tablename__ = "organizations"
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="organization", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=generate_uuid)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="member") # admin, member
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="users")

class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True, default=generate_uuid)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="projects")
    queues = relationship("Queue", back_populates="project", cascade="all, delete-orphan")

class RetryPolicy(Base):
    __tablename__ = "retry_policies"
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    strategy = Column(Enum(RetryStrategy), default=RetryStrategy.FIXED)
    max_retries = Column(Integer, default=3)
    base_delay_ms = Column(Integer, default=1000)

class Queue(Base):
    __tablename__ = "queues"
    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    concurrency_limit = Column(Integer, default=10)
    priority = Column(Integer, default=1)
    is_paused = Column(Boolean, default=False)
    retry_policy_id = Column(String, ForeignKey("retry_policies.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="queues")
    retry_policy = relationship("RetryPolicy")
    jobs = relationship("Job", back_populates="queue", cascade="all, delete-orphan")

class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"
    id = Column(String, primary_key=True, default=generate_uuid)
    queue_id = Column(String, ForeignKey("queues.id", ondelete="CASCADE"), nullable=False)
    cron_expression = Column(String, nullable=False)
    payload = Column(JSONB, nullable=True)
    is_active = Column(Boolean, default=True)
    next_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True, default=generate_uuid)
    queue_id = Column(String, ForeignKey("queues.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(JobStatus), default=JobStatus.QUEUED, index=True)
    payload = Column(JSONB, nullable=True)
    priority = Column(Integer, default=1)
    
    # Scheduling & Concurrency
    scheduled_at = Column(DateTime, default=datetime.utcnow, index=True)
    claimed_by = Column(String, ForeignKey("workers.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Retries
    attempts = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    queue = relationship("Queue", back_populates="jobs")
    executions = relationship("JobExecution", back_populates="job", cascade="all, delete-orphan")
    logs = relationship("JobLog", back_populates="job", cascade="all, delete-orphan")

class Worker(Base):
    __tablename__ = "workers"
    id = Column(String, primary_key=True, default=generate_uuid)
    hostname = Column(String, nullable=False)
    status = Column(String, default="active") # active, offline
    started_at = Column(DateTime, default=datetime.utcnow)
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    
    heartbeats = relationship("WorkerHeartbeat", back_populates="worker", cascade="all, delete-orphan")

class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    id = Column(String, primary_key=True, default=generate_uuid)
    worker_id = Column(String, ForeignKey("workers.id", ondelete="CASCADE"), nullable=False, index=True)
    cpu_usage = Column(Integer, nullable=True)
    memory_usage = Column(Integer, nullable=True)
    active_jobs = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.utcnow)

    worker = relationship("Worker", back_populates="heartbeats")

class JobExecution(Base):
    __tablename__ = "job_executions"
    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    queue_id = Column(String, nullable=False, index=True) # Denormalized for faster querying
    worker_id = Column(String, ForeignKey("workers.id", ondelete="SET NULL"), nullable=True)
    status = Column(Enum(JobStatus), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    job = relationship("Job", back_populates="executions")

class JobLog(Base):
    __tablename__ = "job_logs"
    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    log_level = Column(String, default="INFO")
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="logs")

class DeadLetterQueue(Base):
    __tablename__ = "dead_letter_queue"
    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, unique=True, nullable=False)
    queue_id = Column(String, nullable=False, index=True)
    payload = Column(JSONB, nullable=True)
    error_summary = Column(Text, nullable=True)
    ai_failure_summary = Column(Text, nullable=True) # Bonus feature field
    failed_at = Column(DateTime, default=datetime.utcnow)
