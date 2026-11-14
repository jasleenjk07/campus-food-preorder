from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CartItem, FoodItem, User
from ..auth.deps import get_current_user
from ..schemas import CartAddRequest, CartUpdateRequest, CartResponse

router = APIRouter(tags=["Cart"])


def _build_cart_response(db: Session, user_id: int) -> dict:
    cart_items = db.query(CartItem).filter(CartItem.user_id == user_id).all()
    response_items = []
    total = 0.0

    for item in cart_items:
        food = db.query(FoodItem).filter(FoodItem.id == item.food_id).first()
        if not food:
            continue

        item_total = food.price * item.quantity
        total += item_total
        response_items.append({
            "food_id": food.id,
            "name": food.name,
            "price": food.price,
            "quantity": item.quantity,
        })

    return {"items": response_items, "total": total}


@router.post("/add", response_model=CartResponse)
def add_to_cart(
    request: CartAddRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    food = db.query(FoodItem).filter(FoodItem.id == request.food_id).first()

    if not food or not food.is_available:
        raise HTTPException(status_code=404, detail="Food item not available")

    if food.stock < request.quantity:
        raise HTTPException(status_code=400, detail="Not enough stock available")

    cart_item = db.query(CartItem).filter(
        CartItem.user_id == current_user.id,
        CartItem.food_id == request.food_id,
    ).first()

    if cart_item:
        cart_item.quantity += request.quantity
    else:
        cart_item = CartItem(
            user_id=current_user.id,
            food_id=request.food_id,
            quantity=request.quantity,
        )
        db.add(cart_item)

    db.commit()
    return _build_cart_response(db, current_user.id)


@router.get("", response_model=CartResponse)
@router.get("/", response_model=CartResponse, include_in_schema=False)
def get_cart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _build_cart_response(db, current_user.id)


@router.put("/update", response_model=CartResponse)
def update_cart(
    request: CartUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart_item = db.query(CartItem).filter(
        CartItem.user_id == current_user.id,
        CartItem.food_id == request.food_id,
    ).first()

    if not cart_item:
        raise HTTPException(status_code=404, detail="Item not found in cart")

    if request.quantity <= 0:
        db.delete(cart_item)
    else:
        cart_item.quantity = request.quantity

    db.commit()
    return _build_cart_response(db, current_user.id)


@router.delete("/delete/{food_id}", response_model=CartResponse)
def delete_cart(
    food_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart_item = db.query(CartItem).filter(
        CartItem.user_id == current_user.id,
        CartItem.food_id == food_id,
    ).first()

    if not cart_item:
        raise HTTPException(status_code=404, detail="Item not found in cart")

    db.delete(cart_item)
    db.commit()
    return _build_cart_response(db, current_user.id)
