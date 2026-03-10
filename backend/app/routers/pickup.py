from fastapi import APIRouter, Depends, HTTPException
from fastapi.background import P
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.pickup_service import generate_pickup_slots
from app.models import User
# from app.auth.roles import require_role

router = APIRouter(tags=["Pickup"])

@router.get("/slots")
def get_pickup_slots(vendor_id: int, db: Session = Depends(get_db)):

    vendor = db.query(User).filter(User.id == vendor_id).first()

    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if vendor.opening_hour is None or vendor.closing_hour is None:
        return {
            "is_open": False,
            "slots": [],
            "next_available": None
        }

    slots = generate_pickup_slots(
        vendor.opening_hour,
        vendor.closing_hour
    )

    return {
        "is_open": True if slots else False,
        "slots": slots,
        "next_available": slots[0] if slots else None
    }