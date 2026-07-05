from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from typing import List, Optional

from app.database import get_db
from app.models import Project, Organization
from app.schemas import ProjectCreate, ProjectResponse

from app.routers.auth import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])

@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(project: ProjectCreate, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_user)):
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

@router.post("/organizations/", status_code=status.HTTP_201_CREATED)
async def create_organization(name: str, db: AsyncSession = Depends(get_db), current_user: str = Depends(get_current_user)):
    new_org = Organization(id=str(uuid.uuid4()), name=name)
    db.add(new_org)
    await db.commit()
    await db.refresh(new_org)
    return {"id": new_org.id, "name": new_org.name}

@router.get("/", response_model=List[ProjectResponse])
async def list_projects(organization_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    if organization_id:
        result = await db.execute(select(Project).where(Project.organization_id == organization_id))
    else:
        result = await db.execute(select(Project))
    return result.scalars().all()
