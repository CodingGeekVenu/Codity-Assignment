import pytest
from httpx import AsyncClient, ASGITransport
import uuid
from app.main import app
from app.models import JobStatus

@pytest.fixture
async def async_client():
    from app.routers.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: "testuser"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

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

@pytest.mark.asyncio
async def test_auth_rejection(setup_org):
    from app.main import app
    from httpx import AsyncClient, ASGITransport
    from app.routers.auth import get_current_user
    
    # Store and remove the global override to test actual auth
    original_override = app.dependency_overrides.get(get_current_user)
    if get_current_user in app.dependency_overrides:
        del app.dependency_overrides[get_current_user]
        
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/projects/", json={"name": "Unauthorized Project", "organization_id": setup_org})
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
        
    # Restore the override for other tests
    if original_override:
        app.dependency_overrides[get_current_user] = original_override

@pytest.mark.asyncio
async def test_queue_pause_resume(async_client: AsyncClient, setup_org):
    org_id = setup_org
    proj_res = await async_client.post("/projects/", json={"name": "Queue Test", "organization_id": org_id})
    project_id = proj_res.json()["id"]
    
    # Create queue
    q_res = await async_client.post("/queues/", json={"name": "P Q", "project_id": project_id, "retry_strategy": "fixed"})
    q_id = q_res.json()["id"]
    
    # Pause queue
    pause_res = await async_client.patch(f"/queues/{q_id}", json={"is_paused": True})
    assert pause_res.status_code == 200
    assert pause_res.json()["is_paused"] == True
    
    # Resume queue
    resume_res = await async_client.patch(f"/queues/{q_id}", json={"is_paused": False})
    assert resume_res.status_code == 200
    assert resume_res.json()["is_paused"] == False

@pytest.mark.asyncio
async def test_batch_jobs_and_validation(async_client: AsyncClient, setup_org):
    org_id = setup_org
    proj_res = await async_client.post("/projects/", json={"name": "Batch Test", "organization_id": org_id})
    project_id = proj_res.json()["id"]
    q_res = await async_client.post("/queues/", json={"name": "B Q", "project_id": project_id, "retry_strategy": "fixed"})
    q_id = q_res.json()["id"]
    
    # Batch Insert
    batch_res = await async_client.post("/jobs/batch", json={
        "jobs": [
            {"queue_id": q_id, "payload": {"t": 1}},
            {"queue_id": q_id, "payload": {"t": 2}}
        ]
    })
    assert batch_res.status_code == 201
    assert len(batch_res.json()) == 2
    
    # Validation Error (Missing queue_id)
    bad_job_res = await async_client.post("/jobs/", json={"priority": 1})
    assert bad_job_res.status_code == 422
