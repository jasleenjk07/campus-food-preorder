from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import FoodCreate, FoodResponse, FoodUpdate
from app.auth.roles import require_role
from app.core.cache import get_cache, set_cache, delete_cache

router = APIRouter(tags=["Menu"])


def _get_owned_food(db: Session, food_id: int, current_user):
    food_item = db.query(models.FoodItem).filter(
        models.FoodItem.id == food_id
    ).first()

    if not food_item:
        raise HTTPException(status_code=404, detail="Food item not found")

    if current_user.role == "VENDOR" and food_item.vendor_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only modify your own menu items",
        )

    return food_item


@router.post("", response_model=FoodResponse)
@router.post("/", response_model=FoodResponse, include_in_schema=False)
def add_food(
    food: FoodCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("ADMIN", "VENDOR")),
):
    new_food = models.FoodItem(
        name=food.name,
        description=food.description,
        price=food.price,
        category=food.category,
        image_url=food.image_url,
        is_available=food.is_available,
        stock=food.stock,
        vendor_id=current_user.id,
    )

    db.add(new_food)
    db.commit()
    delete_cache("menu:all")
    db.refresh(new_food)
    return new_food


@router.put("/{food_id}", response_model=FoodResponse)
def update_food(
    food_id: int,
    food: FoodUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("ADMIN", "VENDOR")),
):
    food_item = _get_owned_food(db, food_id, current_user)
    updates = food.model_dump(exclude_unset=True)

    for key, value in updates.items():
        setattr(food_item, key, value)

    db.commit()
    db.refresh(food_item)
    delete_cache("menu:all")
    return food_item


@router.delete("/{food_id}")
def delete_food(
    food_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("ADMIN", "VENDOR")),
):
    food_item = _get_owned_food(db, food_id, current_user)

    # Soft-delete to avoid FK errors on past orders/carts.
    food_item.is_available = False
    food_item.stock = 0
    db.commit()
    delete_cache("menu:all")

    return {"message": "Food item removed from menu successfully"}


@router.get("", response_model=list[FoodResponse])
@router.get("/", response_model=list[FoodResponse], include_in_schema=False)
def get_menu(db: Session = Depends(get_db)):
    cache_key = "menu:all"
    cached_data = get_cache(cache_key)
    if cached_data:
        return cached_data

    menu_items = db.query(models.FoodItem).filter(
        models.FoodItem.is_available == True
    ).all()

    set_cache(
        cache_key,
        [FoodResponse.model_validate(item).model_dump() for item in menu_items],
    )
    return menu_items


@router.get("/vendor/{vendor_id}")
def get_vendor_menu(vendor_id: int, db: Session = Depends(get_db)):
    vendor = db.query(models.User).filter(
        models.User.id == vendor_id,
        models.User.role == "VENDOR",
    ).first()

    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    menu_items = db.query(models.FoodItem).filter(
        models.FoodItem.vendor_id == vendor_id,
        models.FoodItem.is_available == True,
    ).all()

    return {
        "vendor": {
            "id": vendor.id,
            "name": vendor.shop_name or vendor.name,
            "description": vendor.category or "Food",
            "is_open": vendor.is_open if vendor.is_open is not None else True,
            "image_url": vendor.logo_url or "",
        },
        "menu": [
            FoodResponse.model_validate(item).model_dump() for item in menu_items
        ],
    }
