import random

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, Header

from sqlalchemy.orm import Session, joinedload #Session represents a database connection

from app.database import get_db #get_db provides a database session per request
from app import models
from app.schemas import OrderCreate, OrderResponse, OrderHistoryResponse, OrderHistoryItem, PaymentMethod, CheckoutRequest, PaymentSummaryResponse, ConfirmPaymentRequest
from app.auth.roles import require_role
from app.utils import create_notification
from app.tasks.notifications import send_notification_task,send_email_notification
from app.core.rate_limiter import limiter
from app.core.order_state import validate_transition
import app.services.pickup_service as pickup_service

router = APIRouter(tags=["Orders"])

@router.post("/", response_model=OrderResponse)
@limiter.limit("10/minute")
async def place_order(
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
        user_id=current_user.id,
        total_price=total_price,
        status="PLACED"
    )

    db.add(new_order)
    db.flush()

    order_item = models.OrderItem(
        order_id=new_order.id,
        food_id=food.id,
        quantity=order.quantity,
        price_at_time=food.price
    )

    db.add(order_item)
    db.commit()
    db.refresh(new_order)

    send_notification_task.delay(
        current_user.id,
        f"Your order #{new_order.id} has been placed successfully"
    )

    send_notification_task.delay(
        food.vendor_id,
        f"New order #{new_order.id} received"
    )

    send_email_notification.delay(
        current_user.id,
        "Order Confirmation - Cravix",
        f"Your order #{new_order.id} has been placed successfully"
    )

    return new_order

@router.get("/me", response_model=list[OrderResponse])
def my_orders(
    db: Session = Depends(get_db),
    current_user = Depends(require_role("USER"))
):
    orders = db.query(models.Order).filter(
        models.Order.user_id == current_user.id
    ).all()

    return orders

@router.get("/vendor", response_model=list[OrderResponse])
def vendor_orders(
    db: Session = Depends(get_db),
    current_user = Depends(require_role("VENDOR"))
):
    return (
        db.query(models.Order)
        .join(models.OrderItem) 
        .join(models.FoodItem) 
        .filter(models.FoodItem.vendor_id == current_user.id)
        .all()
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
        db.query(models.Order) 
        .join(models.OrderItem)                             #FROM orders
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

    order.status = "PREPARING"
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
        .join(models.OrderItem)
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

    order.status = "CANCELLED"

    #RESTORE STOCK
    for item in order.items:
        food = db.query(models.FoodItem).filter(
            models.FoodItem.id == item.food_id
        ).with_for_update().first()

        food.stock += item.quantity

        # Notify each vendor (in case of multi-vendor future)
        create_notification(
            db,
            food.vendor_id,
            f"Order #{order.id} was cancelled"
        )

    db.commit()
    db.refresh(order)

    create_notification(
        db, 
        order.user_id,
        f"Your order #{order.id} was cancelled"
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

@router.post("/checkout")
def checkout(
    request: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_role("USER"))
):
    cart_items = db.query(models.CartItem).filter(
        models.CartItem.user_id == current_user.id
    ).all()

    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Get vendor from first cart item (single vendor assumption for now)
    first_food = db.query(models.FoodItem).filter(
        models.FoodItem.id == cart_items[0].food_id
    ).first()

    if not first_food:
        raise HTTPException(status_code=404, detail="Vendor not found")

    vendor = db.query(models.User).filter(
        models.User.id == first_food.vendor_id,
        models.User.role == "VENDOR"
    ).first()

    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if vendor.opening_hour is None or vendor.closing_hour is None:
        raise HTTPException(
            status_code=400,
            detail="Vendor is not configured yet"
        )

    # Validate pickup time
    try:
        available_slots = pickup_service.generate_pickup_slots(
            opening_hour=vendor.opening_hour,
            closing_hour=vendor.closing_hour
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        parsed_time = datetime.strptime(request.pickup_time, "%I:%M %p")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid time format (use HH:MM AM/PM)"
        )

    # Allow custom time if slots are empty (vendor closed) TEMPORARY FOR CHECKING THE FRONTEND
    # if available_slots:
    #     if request.pickup_time not in available_slots:
    #         raise HTTPException(
    #             status_code=400,
    #             detail="Selected time is not available"
    #         )

    # Create Order
    order = models.Order(
        user_id=current_user.id,
        status="PLACED",
        total_price=0,
        pickup_time=parsed_time
    )
    
    db.add(order)
    db.flush()

    total = 0

    for item in cart_items:
        food = db.query(models.FoodItem).filter(
            models.FoodItem.id == item.food_id
        ).with_for_update().first()

        if not food:
            raise HTTPException(status_code=404, detail="Food not found")

        if not food.is_available:
            raise HTTPException(
                status_code=400,
                detail=f"{food.name} is currently unavailable"
            )

        if food.stock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough stock for {food.name}"
            )

        food.stock -= item.quantity

        order_item = models.OrderItem(
            order_id=order.id,
            food_id=food.id,
            quantity=item.quantity,
            price_at_time=food.price
        )

        total += food.price * item.quantity
        db.add(order_item)

    order.total_price = total

    db.query(models.CartItem).filter(
        models.CartItem.user_id == current_user.id
    ).delete()

    db.commit()

    return {
        "order_id": order.id,
        "status": order.status,
        "pickup_time": order.pickup_time,
        "total": total
    }

@router.put("/vendor/hours")
def update_vendor_hours(
    request: models.VendorHoursUpdate,
    db: Session = Depends(get_db),
    vendor = Depends(require_role("VENDOR"))
):
    # Business validation
    if request.closing_hour <= request.opening_hour:
        raise HTTPException(
            status_code=400,
            detail="Closing hour must be greater than opening hour"
        )

    # Update vendor hours
    vendor.opening_hour = request.opening_hour
    vendor.closing_hour = request.closing_hour

    db.commit()
    db.refresh(vendor)

    return {
        "message": "Working hours updated successfully",
        "opening_hour": vendor.opening_hour,
        "closing_hour": vendor.closing_hour
    }

@router.get("/vendors/{vendor_id}/pickup-slots")
def get_vendor_pickup_slots(
    vendor_id: int,
    db: Session = Depends(get_db)
):
    print(f"Vendor ID: {vendor_id}")
    vendor = db.query(models.User).filter(
        models.User.id == vendor_id,
        models.User.role == "VENDOR"
    ).first()

    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if vendor.opening_hour is None or vendor.closing_hour is None:
        raise HTTPException(status_code=400, detail="Vendor working hours not configured")

    slots = pickup_service.generate_pickup_slots(
        opening_hour=vendor.opening_hour,
        closing_hour=vendor.closing_hour
    )

    return {
        "is_open": len(slots) > 0,
        "next_available": slots[0] if slots else None,
        "slots": slots
    }

@router.get("/payment-summary", response_model=PaymentSummaryResponse)
def get_payment_summary(
    db: Session = Depends(get_db),
    current_user = Depends(require_role("USER"))
):
    order = db.query(models.Order).filter(
        models.Order.user_id == current_user.id,
        models.Order.status == "PLACED"
    ).order_by(models.Order.id.desc()).first()

    if not order:
        raise HTTPException(status_code=400, detail="No pending order found")

    order_items = db.query(models.OrderItem).filter(
        models.OrderItem.order_id == order.id
    ).all()

    items = []

    for item in order_items:
        food = db.query(models.FoodItem).filter(
            models.FoodItem.id == item.food_id
        ).first()

        items.append({
            "name": food.name,
            "quantity": item.quantity,
            "price": item.price_at_time * item.quantity
        })

    item_total = sum(item.price_at_time * item.quantity for item in order_items)
    service_fee = 10.0
    final_total = item_total + service_fee

    return {
        "items": items,
        "item_total": item_total,
        "service_fee": service_fee,
        "final_total": final_total,
        "item_count": sum(item.quantity for item in order_items), 
        "wallet_balance": current_user.wallet_balance,
        "wallet_enabled": True,
        "upi_enabled": True,
        "card_enabled": True
    }

@router.get("/{order_id}/confirmation")
def get_order_confirmation(
    order_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_role("USER"))
):
    order = db.query(models.Order).filter(
        models.Order.id == order_id,
        models.Order.user_id == current_user.id
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return {
        "order_id": f"ORD-2026-{order.id:06d}",
        "pickup_time": order.pickup_time.strftime("%I:%M %p") if order.pickup_time else "N/A",
        "pickup_location": "Campus Cafe",
        "counter": "Counter #3",
        "preparation_time": "15-20 minutes"
    }

@router.post("/confirm-payment")
def confirm_payment(
    data: ConfirmPaymentRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_role("USER"))
):
    order = db.query(models.Order).filter(
        models.Order.user_id == current_user.id,
        models.Order.status == "PLACED"
    ).order_by(models.Order.id.desc()).first()

    if not order:
        raise HTTPException(status_code=400, detail="No pending order found")

    item_total = order.total_price
    service_fee = 10.0
    final_total = item_total + service_fee
    
    if data.payment_method == PaymentMethod.WALLET:
        if current_user.wallet_balance < final_total:
            raise HTTPException(status_code=400, detail="Insufficient wallet balance")
        
        current_user.wallet_balance -= final_total

    order.is_paid = True
    order.status = "PAID"

    db.commit()

    return {
        "order_id": order.id
    }

@router.get("/history", response_model=list[OrderHistoryResponse])
async def get_order_history(
    db: Session = Depends(get_db),
    current_user = Depends(require_role("USER"))
):
    orders = db.query(models.Order).options(
        joinedload(models.Order.items)
        .joinedload(models.OrderItem.food)
        .joinedload(models.FoodItem.vendor)
    ).filter(
        models.Order.user_id == current_user.id
    ).order_by(models.Order.created_at.desc()).all()

    order_history = []

    for order in orders:
        total_items = sum(item.quantity for item in order.items)

        items = []

        for item in order.items:
            items.append({
                "food_name": item.food.name,
                "quantity": item.quantity,
                "price_at_time": item.price_at_time
            })

        vendor_name = None
        if order.items and order.items[0].food and order.items[0].food.vendor:
            vendor_name = order.items[0].food.vendor.name

        order_history.append({
            "order_id": order.id,
            "vendor_name": vendor_name,
            "total_items": total_items,
            "total_price": order.total_price,
            "status": order.status,
            "pickup_time": str(order.pickup_time if order.pickup_time else order.created_at),
            "is_paid": order.is_paid,
            "payment_method": order.payment_method,
            "created_at": str(order.created_at),
            "items": items
        })

    return order_history

@router.get("/{order_id}/track")
def track_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_role("USER", "VENDOR", "ADMIN"))
):
    order = db.query(models.Order).filter(
        models.Order.id == order_id
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if current_user.role == "USER" and order.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your order")

    if current_user.role == "VENDOR":
        vendor_order = (
            db.query(models.Order)
            .join(models.OrderItem)
            .join(models.FoodItem)
            .filter(
                models.Order.id == order_id,
                models.FoodItem.vendor_id == current_user.id
            )
            .first()
        )

        if not vendor_order:
            raise HTTPException(status_code=403, detail="Not your order")

    return {
    "order_id": f"ORD-2026-{order.id:06d}",
    "status": order.status,
    "token": order.id + 100000,  
    "total": order.total_price,

    "items": [
        {
            "name": item.food.name,
            "quantity": item.quantity,
            "price": item.price_at_time
        }
        for item in order.items
    ],

    "timeline": [
        {
            "title": "Order Placed",
            "time": str(order.created_at.strftime("%I:%M %p")),
            "is_completed": True,
            "is_current": order.status == "PLACED"
        },
        {
            "title": "Preparing",
            "time": "",
            "is_completed": order.status in ["PREPARING", "READY", "DELIVERED"],
            "is_current": order.status == "PREPARING"
        },
        {
            "title": "Ready for Pickup",
            "time": "",
            "is_completed": order.status in ["READY", "DELIVERED"],
            "is_current": order.status == "READY"
        },
        {
            "title": "Completed",
            "time": "",
            "is_completed": order.status == "DELIVERED",
            "is_current": order.status == "DELIVERED"
        }
    ]
}