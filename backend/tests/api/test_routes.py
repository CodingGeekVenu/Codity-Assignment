import pytest
from httpx import AsyncClient, ASGITransport
import uuid
from app.main import app
from app.models import JobStatus

@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def setup_org():
    from app.database import AsyncSessionLocal
    from app.models import Organization
    org_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as session:
        org = Organization(id=org_id, name="Test Org")
        session.add(org)
        await session.commit()
    return org_id

@pytest.mark.asyncio
async def test_projects_queues_jobs_flow(async_client: AsyncClient, setup_org):
    # 1. Create a Project
    org_id = setup_org
    proj_response = await async_client.post("/projects/", json={"name": "Test Project", "organization_id": org_id})
    assert proj_response.status_code == 201
    project_id = proj_response.json()["id"]

    # 2. Create a Queue
    queue_response = await async_client.post("/queues/", json={
        "name": "Test Queue",
        "project_id": project_id,
        "concurrency_limit": 5,
        "retry_strategy": "fixed"
    })
    assert queue_response.status_code == 201
    queue_id = queue_response.json()["id"]

    # 3. Create a Job
    job_response = await async_client.post("/jobs/", json={
        "queue_id": queue_id,
        "priority": 1,
        "payload": {"task": "test_api_flow"}
    })
    assert job_response.status_code == 201
    job_id = job_response.json()["id"]
    assert job_response.json()["status"] == JobStatus.QUEUED.value

    # 4. Fetch the Job
    get_job_response = await async_client.get(f"/jobs/{job_id}")
    assert get_job_response.status_code == 200
    assert get_job_response.json()["id"] == job_id
    assert get_job_response.json()["status"] == JobStatus.QUEUED.value
