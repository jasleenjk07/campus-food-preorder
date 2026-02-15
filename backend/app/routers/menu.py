from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import FoodCreate, FoodResponse
from app.auth.roles import require_role
from app.core.cache import get_cache, set_cache, delete_cache

from fastapi import HTTPException

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

    delete_cache("menu:all")

    db.refresh(new_food)

    return new_food

@router.put("/{food_id}, response_model=FoodResponse")
def update_food(
    food_id: int,
    food: FoodCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_role("ADMIN", "VENDOR"))
):
    food_item = db.query(models.FoodItem).filter(models.FoodItem.id == food_id).first()

    if not food_item:
        return HTTPException(
            status_code=404,
            detail="Food item not found"
        )
    
    food_item.name = food.name
    food_item.description = food.description
    food_item.price = food.price

    db.commit()
    db.refresh(food_item)

    #Invalidate the cache after updating the food item
    delete_cache("menu:all")

    return food_item

@router.delete("/{food_id}")
def delete_food(
    food_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_role("ADMIN", "VENDOR"))
):
    food_item = db.query(models.FoodItem).filter(models.FoodItem.id == food_id).first()

    if not food_item:
        return HTTPException(
            status_code=404,
            detail="Food item not found"
        )
    
    db.delete(food_item)
    db.commit()

    #Invalidate the cache after deleting the food item
    delete_cache("menu:all")

    return {"message": "Food item deleted successfully"}

@router.get("/", response_model=list[FoodResponse])
def get_menu(db: Session = Depends(get_db)):
    cache_key = "menu:all" #Redis key where menu is stored

    cached_data = get_cache(cache_key)
    if cached_data:
        return cached_data

    menu_items = db.query(models.FoodItem).all() #Fetch all food items from database

    set_cache(
        cache_key, 
        [FoodResponse.model_validate(item).model_dump() for item in menu_items]
    )

    return menu_items