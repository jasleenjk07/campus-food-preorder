from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.auth.roles import require_role
from app.schemas import UserPublic

router = APIRouter(tags=["Admin"])


@router.get("/users", response_model=list[UserPublic])
def get_all_users(
    db: Session = Depends(get_db),
    admin=Depends(require_role("ADMIN")),
):
    return db.query(models.User).all()


@router.get("/dashboard")
def admin_dashboard(admin=Depends(require_role("ADMIN"))):
    return {"message": "Welcome Admin"}
