from fastapi import APIRouter, Depends, UploadFile, File
import shutil
import os

from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import VendorProfileResponse, VendorProfileUpdate, BankDetailsResponse, BankDetailsUpdate
from app.auth.roles import require_role

router = APIRouter(tags=["vendor"])

UPLOAD_DIR = "uploads"

@router.get("/profile", response_model=VendorProfileResponse)
def get_vendor_profile(
    db: Session = Depends(get_db),
    vendor = Depends(require_role("VENDOR"))
):
    return {
        "name": vendor.name,
        "shop_name": vendor.shop_name,
        "email": vendor.email,
        "phone": vendor.phone,
        "address": vendor.address,
        "logo_url": vendor.logo_url,
        "is_open": vendor.is_open,
        "opening_hour": vendor.opening_hour,
        "closing_hour": vendor.closing_hour
    }

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

@router.post("/upload/image")
def upload_image(file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok = True)

    file_path = f'{UPLOAD_DIR}/{file.filename}'

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "url": f"http://10.0.2.2:8000/{file_path}"
    }