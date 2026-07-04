from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.get("/")
async def get_auth():
    return {"message": "auth endpoint"}
