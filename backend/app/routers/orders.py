import random

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, Header

from sqlalchemy.orm import Session #Session represents a database connection

from app.database import get_db #get_db provides a database session per request
from app import models
from app.schemas import OrderCreate, OrderResponse, PaymentMethod
from app.auth.roles import require_role
from app.utils import create_notification

from app.core.rate_limiter import limiter
from app.core.order_state import validate_transition

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.post("/", response_model=OrderResponse)
@limiter.limit("10/minute")
def place_order(
    request: Request,
    order: OrderCreate,
    background_tasks: BackgroundTasks, #It allows you to run something after the response is returned.
    db: Session = Depends(get_db),
    current_user = Depends(require_role("USER"))
):
    food = (
        db.query(models.FoodItem)
        .filter(
            models.FoodItem.id == order.food_id,
            models.FoodItem.is_available == True
        )
        .with_for_update()
        .first()
    )

    if not food:
        raise HTTPException(status_code=404, detail="Food item not found")

    if food.stock < order.quantity:
        raise HTTPException(
            status_code=400,
            detail="Not enough stock available"
        )

    food.stock -= order.quantity

    total_price = food.price * order.quantity

    new_order = models.Order(
        user_id = current_user.id,
        food_id = food.id,
        quantity = order.quantity,
        total_price = total_price
    )

    db.add(new_order)
    db.commit()
    db.refresh(new_order)


    background_tasks.add_task(
        create_notification,
        db,
        current_user.id,
        f"Your order #{new_order.id} has been placed."
    )

    background_tasks.add_task(
        create_notification,
        db,
        food.vendor_id,
        f"New order #{new_order.id} received"
    )

    return new_order

@router.get("/me", response_model=list[OrderResponse])
def my_orders(
    db: Session = Depends(get_db),
    current_user = Depends(require_role("USER"))
):
    return db.query(models.Order).filter(
        models.Order.user_id == current_user.id
    ).all()

@router.get("/vendor", response_model=list[OrderResponse])
def vendor_orders(
    db: Session = Depends(get_db),
    current_user = Depends(require_role("VENDOR"))
):
    return (
        db.query(models.Order) #Start querying the orders table
        .join(models.FoodItem) #SQL JOIN between:orders.food_id and food_items.id. This allows access to food-related columns (like vendor_id)
        .filter(models.FoodItem.vendor_id == current_user.id) #Restrict results to orders where the food item belongs to the logged-in vendor
        .all() #Returns a list of orders and empty if no orders are found
    )

@router.get("/admin", response_model=list[OrderResponse])
def all_orders(
    db: Session = Depends(get_db),
    admin = Depends(require_role("ADMIN"))
):
    return db.query(models.Order).all()

@router.get("/ping")
def orders_ping():
    return {"status": "orders alive"}

@router.put("/{order_id}/prepare", response_model=OrderResponse) #This API lets a VENDOR change an order’s status from PLACED → PREPARING
def prepare_order(
    order_id: int,
    db: Session = Depends(get_db),
    vendor = Depends(require_role("VENDOR")) #Only users with role VENDOR can access this
):
    order = (                                               #SELECT orders.*
        db.query(models.Order)                              #FROM orders
        .join(models.FoodItem)                             #JOIN food_items ON orders.food_id = food_items.id
        .filter(
            models.Order.id == order_id,                    #WHERE orders.id = :order_id
            models.FoodItem.vendor_id == vendor.id          #AND food_items.vendor_id = :current_vendor_id
        )
        .first()                                           #Returns the first result or None if no match is found   
    )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if not order.is_paid:
        raise HTTPException(status_code=400, detail="Order must be paid before preparation")

    validate_transition(order.status, "PREPARING") #Moves order from PLACED → PREPARING
    db.commit()
    db.refresh(order)

    create_notification(
        db, 
        order.user_id,
        f"Your order #{order.id} is being prepared"
    )
    return order

@router.put("/{order_id}/deliver", response_model=OrderResponse)
def deliver_order(
    order_id: int,
    db: Session = Depends(get_db),
    vendor = Depends(require_role("VENDOR")) #Only users with role VENDOR can call this
):
    order =(
        db.query(models.Order)
        .join(models.FoodItem)
        .filter(
            models.Order.id == order_id,
            models.FoodItem.vendor_id == vendor.id
        )
        .first()
    )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    validate_transition(order.status, "DELIVERED")
    
    order.status = "DELIVERED" #Marks the order as completed
    # Auto-deduct for Pay Later
    if order.payment_method == "PAY_LATER":
        order.is_paid = True

    db.commit()
    db.refresh(order)

    create_notification(
        db,
        order.user_id,
        f"Your order #{order.id} has been delivered 🚚"
    )

    return order

@router.put("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_role("USER", "ADMIN"))
):
    order = db.query(models.Order).filter(
        models.Order.id == order_id
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # USER rule
    if current_user.role == "USER":
        if order.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your order")

        if order.status != "PLACED":
            raise HTTPException(
                status_code=400,
                detail="Order cannot be cancelled after preparation"
            )
    
    # ADMIN can cancel anytime
    validate_transition(order.status, "CANCELLED")

    db.commit()
    db.refresh(order)

    create_notification(
        db, 
        order.user_id,
        f"Your order #{order.id} was cancelled"
    )

    create_notification(
        db,
        order.food.vendor_id,
        f"Order #{order.id} was cancelled"
    )

    return order

@router.post("/{order_id}/pay", response_model=OrderResponse)
def pay_for_order(
    order_id: int,
    payment_method: PaymentMethod = PaymentMethod.UPI_INAPP,
    idempotency_key: str = Header(...), # Required header, Client must send it
    db: Session = Depends(get_db),
    current_user = Depends(require_role("USER"))
):
    order = db.query(models.Order).filter(
        models.Order.id == order_id,
        models.Order.user_id == current_user.id
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.is_paid:
        raise HTTPException(status_code=400, detail="Order already paid")

    validate_transition(order.status, "PAID")

    existing_order = db.query(models.Order).filter(
        models.Order.idempotency_key == idempotency_key
    ).first()

    if existing_order:
        return existing_order

    # 💳 Payment simulation
    # 80% success, 20% failure
    payment_success = random.choice([True, True, True, True, False])

    # Immediate payments → paid now
    if payment_method in {
        PaymentMethod.UPI_INAPP,
        PaymentMethod.CARD,
        PaymentMethod.WALLET
    }:
        if not payment_success:
            create_notification(
                db, 
                current_user.id,
                f"Payment failed for order #{order.id}"
            )
            raise HTTPException(
                status_code=400,
                detail="Payment failed. Please try again"
            )
            
        order.is_paid = True
        order.status = "PAID"

    # COD / PAY_LATER → paid after delivery
    else:
        order.is_paid = False
    
    order.payment_method = payment_method.value
    order.idempotency_key = idempotency_key
    
    db.commit()
    db.refresh(order)

    create_notification(
        db,
        current_user.id,
        f"Payment successful for order #{order.id}"
    )

    create_notification(
        db,
        order.food.vendor_id,
        f"Order #{order.id} has been paid"
    )

    return order