from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Union
from fastapi.security import OAuth2PasswordRequestForm

from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.utils import hash_password, verify_password
from app.auth.jwt import create_access_token
from app.schemas import (
    LoginResponse,
    LoginRequest,
    UserPrivate,
    VendorPrivate,
    UserCreate,
    UserRole,
)
from app.auth.roles import require_role
from app.core.rate_limiter import limiter

router = APIRouter(tags=["Auth"])


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _build_login_response(user: models.User) -> LoginResponse:
    token = create_access_token({"user_id": user.id, "role": user.role})
    if user.role == "VENDOR":
        user_data = VendorPrivate.model_validate(user)
    else:
        user_data = UserPrivate.model_validate(user)
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=user_data,
    )


@router.post("/register", response_model=Union[UserPrivate, VendorPrivate])
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    email = _normalize_email(user.email)

    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Cannot self-register as ADMIN",
        )

    existing_user = db.query(models.User).filter(
        models.User.email == email
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = models.User(
        name=user.name.strip(),
        email=email,
        password_hash=hash_password(user.password),
        role=user.role.value,
        university_id=user.university_id,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    if new_user.role == "VENDOR":
        return VendorPrivate.model_validate(new_user)
    return UserPrivate.model_validate(new_user)


@router.post("/create-user", response_model=Union[UserPrivate, VendorPrivate])
def create_user_by_admin(
    user: UserCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_role("ADMIN")),
):
    email = _normalize_email(user.email)

    existing_user = db.query(models.User).filter(
        models.User.email == email
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = models.User(
        name=user.name.strip(),
        email=email,
        password_hash=hash_password(user.password),
        role=user.role.value,
        university_id=user.university_id,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    if new_user.role == "VENDOR":
        return VendorPrivate.model_validate(new_user)
    return UserPrivate.model_validate(new_user)


@router.post("/login", response_model=LoginResponse)
@limiter.limit("20/minute")
def login_user(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """OAuth2 form login (Swagger / form clients). username = email."""
    email = _normalize_email(form_data.username)
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return _build_login_response(user)


@router.post("/login/json", response_model=LoginResponse)
@limiter.limit("20/minute")
def login_user_json(
    request: Request,
    credentials: LoginRequest,
    db: Session = Depends(get_db),
):
    """JSON login for Android / mobile clients."""
    email = _normalize_email(credentials.email)
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return _build_login_response(user)
