from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.dependencies import get_current_user

router = APIRouter(tags=["Vendor"])

@router.put("/vendor/profile")
def update_vendor_profile(
    data: dict, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "VENDOR":
        raise HTTPException(status_code=403, detail="Not a vendor")

    current_user.shop_name = data.get("shop_name")
    current_user.category = data.get("category")
    current_user.logo_url = data.get("logo_url")

    db.commit()
    db.refresh(current_user)

    return {"message": "Profile updated successfully"}