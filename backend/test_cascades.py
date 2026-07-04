import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.config import settings
from app.models import Organization, Project, Queue, Job, JobStatus

async def run_cascade_test():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    org_id = str(uuid.uuid4())
    proj_id = str(uuid.uuid4())
    queue_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    
    async with AsyncSessionLocal() as session:
        session.add(Organization(id=org_id, name="Cascade Test Org"))
        session.add(Project(id=proj_id, organization_id=org_id, name="Cascade Proj"))
        session.add(Queue(id=queue_id, project_id=proj_id, name="Cascade Q"))
        session.add(Job(id=job_id, queue_id=queue_id, status=JobStatus.QUEUED))
        await session.commit()
        
        # Verify exists
        res = await session.execute(text(f"SELECT COUNT(*) FROM jobs WHERE id = '{job_id}'"))
        print(f"Jobs before delete: {res.scalar()}")
        
        # Delete project
        await session.execute(text(f"DELETE FROM projects WHERE id = '{proj_id}'"))
        await session.commit()
        
        # Verify cascade
        res = await session.execute(text(f"SELECT COUNT(*) FROM jobs WHERE id = '{job_id}'"))
        print(f"Jobs after delete: {res.scalar()}")
        
        # Clean up org
        await session.execute(text(f"DELETE FROM organizations WHERE id = '{org_id}'"))
        await session.commit()
        
if __name__ == "__main__":
    asyncio.run(run_cascade_test())
