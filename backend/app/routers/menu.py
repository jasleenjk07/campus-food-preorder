from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import FoodCreate, FoodResponse
from app.auth.roles import require_role

router = APIRouter(prefix="/menu", tags=["Menu"])

@router.post("/", response_model=FoodResponse)
def add_food(
    food: FoodCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_role("ADMIN", "VENDOR"))
):
    new_food = models.FoodItem(
        name = food.name,
        description = food.description,
        price = food.price,
        vendor_id = current_user.id #Automatically links food to the logged-in vendor/admin
    )

    db.add(new_food)
    db.commit()
    db.refresh(new_food)

    return new_food

@router.get("/", response_model=list[FoodResponse])
def list_food(db: Session = Depends(get_db)):
    return db.query(models.FoodItem).filter(
        models.FoodItem.is_available == True
    ).all()