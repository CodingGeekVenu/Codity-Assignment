from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from typing import List

from app.database import get_db
from app.models import Project, Organization
from app.schemas import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])

@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(project: ProjectCreate, db: AsyncSession = Depends(get_db)):
    # Check if org exists (optional but good practice)
    org_query = await db.execute(select(Organization).where(Organization.id == project.organization_id))
    if not org_query.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Organization not found")
        
    new_project = Project(
        id=str(uuid.uuid4()),
        name=project.name,
        organization_id=project.organization_id
    )
    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)
    return new_project

@router.get("/", response_model=List[ProjectResponse])
async def list_projects(organization_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.organization_id == organization_id))
    return result.scalars().all()
