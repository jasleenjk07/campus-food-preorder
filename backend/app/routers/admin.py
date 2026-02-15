from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.auth.roles import require_role
from app.auth.roles import require_role

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/users")
def get_all_users(
    db: Session = Depends(get_db),
    admin = Depends(require_role("ADMIN"))
):
    return db.query(models.User).all()

@router.get("/dashboard")
def admin_dashboard(
    admin = Depends(require_role("ADMIN"))
):
    return {"message": "Welcome Admin"}

@router.post("/menu")
def add_menu_item(
    vendor = Depends(require_role("VENDOR"))
):
    return {"message": "Food item added"}

@router.post("/orders")
def place_order(
    user = Depends(require_role("USER"))
):
    return {"message": "Order placed"}