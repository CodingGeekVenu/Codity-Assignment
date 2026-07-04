routers = ['jobs', 'queues', 'projects', 'auth']
for r in routers:
    with open(f'app/routers/{r}.py', 'w') as f:
        f.write(f'''from fastapi import APIRouter

router = APIRouter(prefix="/{r}", tags=["{r.capitalize()}"])

@router.get("/")
async def get_{r}():
    return {{"message": "{r} endpoint"}}
''')
