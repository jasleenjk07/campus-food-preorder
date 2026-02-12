from fastapi import APIRouter, Depends
from app.auth.deps import get_current_user #JWT verification logic
from app.schemas import UserResponse
from app import models

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me", response_model=UserResponse)
def get_my_profile(
    current_user: models.User = Depends(get_current_user)
):
    return current_user