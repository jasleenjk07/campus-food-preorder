from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models

router = APIRouter(tags=["Home"])

@router.get("/vendors")
def get_home_vendors(
    db: Session = Depends(get_db)
):
    vendors = db.query(models.User).filter(
        models.User.role == "VENDOR"
    ).all()

    result = []

    for vendor in vendors:
        result.append({
            "id": vendor.id,
            "shop_name": vendor.shop_name,
            "category": vendor.category,
            "logo_url": vendor.logo_url,
            "is_open": vendor.is_open if vendor.is_open is not None else True,
            "delivery_time": "10-15 min"
        })
        
    return result