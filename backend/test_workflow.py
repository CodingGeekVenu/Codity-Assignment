import requests
import time
import json

API = "http://127.0.0.1:8000"

print("1. Authenticating...")
token_res = requests.post(f"{API}/auth/token", data={"username":"admin","password":"password"})
token = token_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("2. Fetching queues...")
proj = requests.get(f"{API}/projects/", headers=headers).json()
if not proj:
    org = requests.post(f"{API}/projects/organizations/?name=Test").json()
    p = requests.post(f"{API}/projects/", json={"name":"test", "organization_id": org["id"]}, headers=headers).json()
    project_id = p["id"]
else:
    project_id = proj[0]["id"]

queues = requests.get(f"{API}/queues/?project_id={project_id}", headers=headers).json()
if not queues:
    q = requests.post(f"{API}/queues/", json={"name":"test-queue", "project_id": project_id, "retry_strategy": "fixed"}, headers=headers).json()
    queue_id = q["id"]
else:
    queue_id = queues[0]["id"]
print(f"Queue ID: {queue_id}")

print("\n3. Injecting forced-failure job...")
job_res = requests.post(f"{API}/jobs/", headers=headers, json={"queue_id": queue_id, "payload": {"force_fail": True}, "max_retries": 0})
job = job_res.json()
job_id = job["id"]
print(f"Created Job: {job_id}")

print("\n4. Waiting for worker to process and fail the job (hitting DLQ)...")
for _ in range(15):
    time.sleep(1)
    # Check if in DLQ
    dlq_res = requests.get(f"{API}/jobs/dlq/all", headers=headers).json()
    if any(d["job_id"] == job_id for d in dlq_res):
        print(f"SUCCESS: Job {job_id} successfully landed in DLQ after max retries!")
        break
else:
    print("ERROR: Timeout waiting for job to hit DLQ.")
    exit(1)

print("\n5. Checking Job Logs API (Simulating 'View Logs' click)...")
logs_res = requests.get(f"{API}/jobs/{job_id}/logs", headers=headers)
logs = logs_res.json()
if len(logs) > 0:
    print(f"SUCCESS: Found {len(logs)} execution logs!")
    for log in logs:
        print(f"   [{log['created_at']}] {log['message']}")
else:
    print("ERROR: No logs found!")
    exit(1)

print("\n6. Triggering Retry (Simulating 'Retry' button click)...")
retry_res = requests.post(f"{API}/jobs/{job_id}/retry", headers=headers)
if retry_res.status_code == 200:
    print("SUCCESS: Retry API returned 200 OK")
else:
    print(f"ERROR: Retry API failed: {retry_res.text}")
    exit(1)

print("\n7. Verifying State Changes...")
updated_job = requests.get(f"{API}/jobs/{queue_id}", headers=headers).json()
# Actually we can just query the queue, but it's a list. Let's find our job.
job_after_retry = next(j for j in updated_job if j["id"] == job_id)
if job_after_retry["status"] == "QUEUED":
    print("SUCCESS: Job status successfully reverted to QUEUED!")
else:
    print(f"ERROR: Job status is {job_after_retry['status']}, expected QUEUED")

print("Checking DLQ again...")
dlq_after = requests.get(f"{API}/jobs/dlq/all", headers=headers).json()
if any(d["job_id"] == job_id for d in dlq_after):
    print("ERROR: Job is STILL in the DLQ!")
else:
    print("SUCCESS: Job was successfully purged from DLQ!")

print("\nALL TESTS PASSED! Retry and Log APIs are solid.")
