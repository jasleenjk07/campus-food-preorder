from fastapi import APIRouter, Depends
from app.auth.deps import get_current_user #JWT verification logic
from app.schemas import UserPublic, VendorPublic
from app import models

router = APIRouter(tags=["Users"])

@router.get("/me")
def get_current_user_details(current_user = Depends(get_current_user)):

    if current_user.role == "VENDOR":
        return VendorPublic.from_orm(current_user)

    return UserPublic.from_orm(current_user)