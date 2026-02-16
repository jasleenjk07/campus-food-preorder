from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm

from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import UserCreate, UserResponse
from app.utils import hash_password
from app.utils import verify_password
from app.auth.jwt import create_access_token
from app.schemas import LoginRequest, LoginResponse
from app.auth.roles import require_role
from app.core.rate_limiter import limiter

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    #Check if user already exists
    existing_user = db.query(models.User).filter(
        models.User.email == user.email
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    #Create new user
    new_user = models.User(
        name=user.name,
        email=user.email,
        password_hash=hash_password(user.password),
        role=user.role,
        university_id=user.university_id,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user

@router.post("/create-user", response_model=UserResponse)
def create_user_by_admin(
    user: UserCreate,
    db: Session = Depends(get_db),
    admin = Depends(require_role("ADMIN"))
):
    new_user = models.User(
        name=user.name,
        email=user.email,
        password_hash=hash_password(user.password),
        role=user.role, #ADMIN can assign
        university_id=user.university_id
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user
    
@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
def login_user(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(
        models.User.email == form_data.username
    ).first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"user_id": user.id, "role": user.role})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }