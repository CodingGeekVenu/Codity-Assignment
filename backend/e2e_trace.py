import asyncio
import httpx
from datetime import datetime

async def run_trace():
    print("Starting End-to-End Trace...")
    
    # Needs to hit the DB directly or use the models to create org if not exist, 
    # but the API doesn't have POST /organizations. 
    # We can just insert an org using sqlalchemy.
    from app.database import AsyncSessionLocal
    from app.models import Organization, Job
    from sqlalchemy import select
    import uuid
    
    org_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as session:
        session.add(Organization(id=org_id, name="Test Org"))
        await session.commit()
        
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        print("1. Creating Project...")
        res = await client.post("/projects/", json={"name": "E2E Project", "organization_id": org_id})
        project = res.json()
        print(f"Project Created: {project['id']}")
        
        print("2. Creating Queue...")
        res = await client.post("/queues/", json={
            "name": "E2E Queue", 
            "project_id": project['id'],
            "retry_strategy": "fixed"
        })
        queue = res.json()
        if "id" not in queue:
            print(f"Failed to create queue: {queue}")
            return
            
        print(f"Queue Created: {queue['id']}")
        
        print("3. Creating Job (Will fail 3 times and hit DLQ)...")
        res = await client.post("/jobs/", json={
            "queue_id": queue['id'],
            "payload": {"task": "e2e_test", "force_fail": True}
        })
        job = res.json()
        job_id = job['id']
        print(f"Job Created: {job_id} | Status: {job['status']}")
        
        print("\nMonitoring Job Status...")
        for _ in range(15):
            await asyncio.sleep(2)
            res = await client.get(f"/jobs/{job_id}")
            j = res.json()
            print(f"[{datetime.utcnow().time()}] Job Status: {j['status']} | Attempts: {j['attempts']}")
            
            if j['status'] == 'FAILED':
                print("\nJob reached FAILED state! Checking DLQ...")
                async with AsyncSessionLocal() as session:
                    dlq_res = await session.execute(text("SELECT ai_failure_summary FROM dead_letter_queue WHERE job_id = :jid"), {"jid": job_id})
                    dlq = dlq_res.fetchone()
                    if dlq:
                        print(f"✅ AI Failure Summary found in DLQ:\n{dlq.ai_failure_summary}")
                    else:
                        print("❌ Job in FAILED state but not in DLQ!")
                break
                
if __name__ == "__main__":
    from sqlalchemy import text
    asyncio.run(run_trace())
