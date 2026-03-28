from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import VendorProfileResponse, VendorProfileUpdate, BankDetailsResponse, BankDetailsUpdate
from app.auth.roles import require_role

router = APIRouter(tags=["vendor"])

@router.get("/profile", response_model=VendorProfileResponse)
def get_vendor_profile(
    db: Session = Depends(get_db),
    vendor = Depends(require_role("VENDOR"))
):
    return vendor

@router.put("/profile")
def update_vendor_profile(
    data: VendorProfileUpdate,
    db: Session = Depends(get_db),
    vendor = Depends(require_role("VENDOR"))
):
    for key, value in data.dict(exclude_unset=True).items():
        setattr(vendor, key, value)

    db.commit()
    db.refresh(vendor)

    return {"message": "Profile updated successfully"}

@router.get("/hours")
def get_vendor_hours(
    vendor = Depends(require_role("VENDOR"))
):
    return {
        "opening_hour": vendor.opening_hour, 
        "closing_hour": vendor.closing_hour
    }

@router.put("/status")
def update_vendor_status(
    is_open: bool,
    db: Session = Depends(get_db),
    vendor = Depends(require_role("VENDOR"))
):
    vendor.is_open = is_open
    db.commit()

    return {
        "message": "Status updated",
        "is_open": vendor.is_open
    }

@router.get("/bank-details", response_model=BankDetailsResponse)
def get_bank_details(
    vendor = Depends(require_role("VENDOR"))
):
    return vendor

@router.put("/bank-details")
def update_bank_details(
    data: BankDetailsUpdate,
    db: Session = Depends(get_db),
    vendor = Depends(require_role("VENDOR"))
):
    vendor.account_holder_name = data.account_holder_name
    vendor.bank_account_number = data.bank_account_number
    vendor.ifsc_code = data.ifsc_code

    db.commit()

    return {"message": "Bank details updated successfully"}