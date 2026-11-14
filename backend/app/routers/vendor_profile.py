import os
import re
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    VendorProfileResponse,
    VendorProfileUpdate,
    BankDetailsResponse,
    BankDetailsUpdate,
)
from app.auth.roles import require_role
from app.config import settings

router = APIRouter(tags=["vendor"])

UPLOAD_DIR = "uploads"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


@router.get("/profile", response_model=VendorProfileResponse)
def get_vendor_profile(
    db: Session = Depends(get_db),
    vendor=Depends(require_role("VENDOR")),
):
    return {
        "name": vendor.name,
        "shop_name": vendor.shop_name,
        "email": vendor.email,
        "phone": vendor.phone,
        "address": vendor.address,
        "logo_url": vendor.logo_url,
        "is_open": vendor.is_open if vendor.is_open is not None else True,
        "opening_hour": vendor.opening_hour,
        "closing_hour": vendor.closing_hour,
    }


@router.put("/profile")
def update_vendor_profile(
    data: VendorProfileUpdate,
    db: Session = Depends(get_db),
    vendor=Depends(require_role("VENDOR")),
):
    updates = data.model_dump(exclude_unset=True)

    opening_hour = updates.get("opening_hour", vendor.opening_hour)
    closing_hour = updates.get("closing_hour", vendor.closing_hour)

    if opening_hour is not None and closing_hour is not None:
        if closing_hour <= opening_hour:
            raise HTTPException(
                status_code=400,
                detail="Closing hour must be greater than opening hour",
            )

    for key, value in updates.items():
        setattr(vendor, key, value)

    db.commit()
    db.refresh(vendor)

    return {
        "message": "Profile updated successfully",
        "shop_name": vendor.shop_name,
        "opening_hour": vendor.opening_hour,
        "closing_hour": vendor.closing_hour,
    }


@router.get("/hours")
def get_vendor_hours(vendor=Depends(require_role("VENDOR"))):
    return {
        "opening_hour": vendor.opening_hour,
        "closing_hour": vendor.closing_hour,
    }


@router.put("/hours")
def update_vendor_hours_profile(
    opening_hour: int,
    closing_hour: int,
    db: Session = Depends(get_db),
    vendor=Depends(require_role("VENDOR")),
):
    if closing_hour <= opening_hour:
        raise HTTPException(
            status_code=400,
            detail="Closing hour must be greater than opening hour",
        )

    vendor.opening_hour = opening_hour
    vendor.closing_hour = closing_hour
    db.commit()

    return {
        "message": "Working hours updated successfully",
        "opening_hour": vendor.opening_hour,
        "closing_hour": vendor.closing_hour,
    }


@router.put("/status")
def update_vendor_status(
    is_open: bool,
    db: Session = Depends(get_db),
    vendor=Depends(require_role("VENDOR")),
):
    vendor.is_open = is_open
    db.commit()

    return {
        "message": "Status updated",
        "is_open": vendor.is_open,
    }


@router.get("/bank-details", response_model=BankDetailsResponse)
def get_bank_details(vendor=Depends(require_role("VENDOR"))):
    return vendor


@router.put("/bank-details")
def update_bank_details(
    data: BankDetailsUpdate,
    db: Session = Depends(get_db),
    vendor=Depends(require_role("VENDOR")),
):
    vendor.account_holder_name = data.account_holder_name
    vendor.bank_account_number = data.bank_account_number
    vendor.ifsc_code = data.ifsc_code
    db.commit()
    return {"message": "Bank details updated successfully"}


@router.post("/upload/image")
def upload_image(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    vendor=Depends(require_role("VENDOR")),
):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    original_name = Path(file.filename or "upload.bin").name
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only image files are allowed (.jpg, .jpeg, .png, .webp, .gif)",
        )

    safe_stem = re.sub(r"[^a-zA-Z0-9_-]", "", Path(original_name).stem)[:40] or "image"
    filename = f"{vendor.id}_{uuid.uuid4().hex}_{safe_stem}{extension}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    public_base = (settings.PUBLIC_BASE_URL or str(request.base_url)).rstrip("/")
    url = f"{public_base}/uploads/{filename}"

    vendor.logo_url = url
    db.commit()

    return {"url": url}
