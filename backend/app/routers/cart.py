from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CartItem, FoodItem
from ..auth.deps import get_current_user
from ..models import User
from ..schemas import CartAddRequest, CartUpdateRequest, CartResponse, CartItemResponse

router = APIRouter(tags=["Cart"])

print("CART ROUTER LOADED")

@router.post("/add", response_model=CartResponse)
def add_to_cart(
    request: CartAddRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    food = db.query(FoodItem).filter(FoodItem.id == request.food_id).first()

    if not food or not food.is_available:
        raise HTTPException(status_code=404, detail="Food item not available")

    cart_item = db.query(CartItem).filter(
        CartItem.user_id == current_user.id, 
        CartItem.food_id == request.food_id
    ).first()

    if cart_item:
        cart_item.quantity += request.quantity
    else:
        cart_item = CartItem(
            user_id=current_user.id,
            food_id=request.food_id,
            quantity=request.quantity
        )
        db.add(cart_item)

    db.commit()
    return get_cart(db=db, current_user=current_user)

@router.get("/", response_model=CartResponse)
def get_cart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cart_items = db.query(CartItem).filter(
        CartItem.user_id == current_user.id
    ).all()

    response_items = []
    total = 0

    for item in cart_items:
        food = db.query(FoodItem).filter(FoodItem.id == item.food_id).first()

        item_total = food.price * item.quantity
        total += item_total

        response_items.append({
            "food_id": food.id,
            "name": food.name,
            "price": food.price,
            "quantity": item.quantity
        })

    return {
        "items": response_items,
        "total": total
    }

@router.put("/update", response_model=CartResponse)
def update_cart(
    request: CartUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cart_item = db.query(CartItem).filter(
        CartItem.user_id == current_user.id,
        CartItem.food_id == request.food_id
    ).first()

    if not cart_item:
        raise HTTPException(status_code=404, detail="Item not found in cart")

    if request.quantity <= 0:
        db.delete(cart_item)
    else:
        cart_item.quantity = request.quantity

    db.commit()
    return get_cart(db=db, current_user=current_user)

@router.delete("/delete/{food_id}", response_model=CartResponse)
def delete_cart(
    food_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cart_item = db.query(CartItem).filter(
        CartItem.user_id == current_user.id,
        CartItem.food_id == food_id
    ).first()

    if not cart_item:
        raise HTTPException(status_code=404, detail="Item not found in cart")

    db.delete(cart_item)
    db.commit()
    
    return get_cart(db=db, current_user=current_user)