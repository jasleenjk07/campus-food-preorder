from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app import models
from app.schemas import (
    OrderCreate,
    OrderResponse,
    OrderHistoryResponse,
    PaymentMethod,
    CheckoutRequest,
    PaymentSummaryResponse,
    ConfirmPaymentRequest,
)
from app.auth.roles import require_role
from app.utils import create_notification
from app.tasks.notifications import send_notification_task, send_email_notification
from app.core.rate_limiter import limiter
from app.core.order_state import validate_transition
import app.services.pickup_service as pickup_service

router = APIRouter(tags=["Orders"])


def _safe_notify_task(user_id: int, message: str):
    try:
        send_notification_task.delay(user_id, message)
    except Exception:
        pass


def _safe_email_task(user_id: int, subject: str, message: str):
    try:
        send_email_notification.delay(user_id, subject, message)
    except Exception:
        pass


def _vendor_id_for_order(order: models.Order) -> int | None:
    if order.vendor_id:
        return order.vendor_id
    if order.items:
        first = order.items[0]
        if first.food is not None:
            return first.food.vendor_id
    return None


@router.post("", response_model=OrderResponse)
@router.post("/", response_model=OrderResponse, include_in_schema=False)
@limiter.limit("10/minute")
async def place_order(
    request: Request,
    order: OrderCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("USER")),
):
    food = (
        db.query(models.FoodItem)
        .filter(
            models.FoodItem.id == order.food_id,
            models.FoodItem.is_available == True,
        )
        .with_for_update()
        .first()
    )

    if not food:
        raise HTTPException(status_code=404, detail="Food item not found")

    if food.stock < order.quantity:
        raise HTTPException(status_code=400, detail="Not enough stock available")

    food.stock -= order.quantity
    total_price = food.price * order.quantity

    new_order = models.Order(
        user_id=current_user.id,
        vendor_id=food.vendor_id,
        total_price=total_price,
        status="PLACED",
    )
    db.add(new_order)
    db.flush()

    db.add(
        models.OrderItem(
            order_id=new_order.id,
            food_id=food.id,
            quantity=order.quantity,
            price_at_time=food.price,
        )
    )
    db.commit()
    db.refresh(new_order)

    create_notification(
        db,
        current_user.id,
        f"Your order #{new_order.id} has been placed successfully",
    )
    if food.vendor_id:
        create_notification(
            db,
            food.vendor_id,
            f"New order #{new_order.id} received",
        )
    _safe_email_task(
        current_user.id,
        "Order Confirmation - Cravix",
        f"Your order #{new_order.id} has been placed successfully",
    )

    return new_order


@router.get("/me", response_model=list[OrderResponse])
def my_orders(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("USER")),
):
    return (
        db.query(models.Order)
        .options(joinedload(models.Order.items))
        .filter(models.Order.user_id == current_user.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )


@router.get("/vendor", response_model=list[OrderResponse])
def vendor_orders(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("VENDOR")),
):
    return (
        db.query(models.Order)
        .options(joinedload(models.Order.items))
        .filter(models.Order.vendor_id == current_user.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )


@router.get("/admin", response_model=list[OrderResponse])
def all_orders(
    db: Session = Depends(get_db),
    admin=Depends(require_role("ADMIN")),
):
    return (
        db.query(models.Order)
        .options(joinedload(models.Order.items))
        .order_by(models.Order.created_at.desc())
        .all()
    )


@router.get("/ping")
def orders_ping():
    return {"status": "orders alive"}


@router.put("/{order_id}/prepare", response_model=OrderResponse)
def prepare_order(
    order_id: int,
    db: Session = Depends(get_db),
    vendor=Depends(require_role("VENDOR")),
):
    order = (
        db.query(models.Order)
        .options(joinedload(models.Order.items).joinedload(models.OrderItem.food))
        .filter(
            models.Order.id == order_id,
            models.Order.vendor_id == vendor.id,
        )
        .first()
    )

    if not order:
        # Fallback for older orders without vendor_id
        order = (
            db.query(models.Order)
            .join(models.OrderItem)
            .join(models.FoodItem)
            .options(joinedload(models.Order.items))
            .filter(
                models.Order.id == order_id,
                models.FoodItem.vendor_id == vendor.id,
            )
            .first()
        )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    deferred_methods = {"COD", "PAY_LATER"}
    if not order.is_paid and order.payment_method not in deferred_methods:
        raise HTTPException(
            status_code=400,
            detail="Order must be paid before preparation",
        )

    validate_transition(order.status, "PREPARING")
    order.status = "PREPARING"
    db.commit()
    db.refresh(order)

    create_notification(
        db,
        order.user_id,
        f"Your order #{order.id} is being prepared",
    )
    return order


@router.put("/{order_id}/deliver", response_model=OrderResponse)
def deliver_order(
    order_id: int,
    db: Session = Depends(get_db),
    vendor=Depends(require_role("VENDOR")),
):
    order = (
        db.query(models.Order)
        .options(joinedload(models.Order.items))
        .filter(
            models.Order.id == order_id,
            models.Order.vendor_id == vendor.id,
        )
        .first()
    )

    if not order:
        order = (
            db.query(models.Order)
            .join(models.OrderItem)
            .join(models.FoodItem)
            .options(joinedload(models.Order.items))
            .filter(
                models.Order.id == order_id,
                models.FoodItem.vendor_id == vendor.id,
            )
            .first()
        )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    validate_transition(order.status, "DELIVERED")
    order.status = "DELIVERED"

    if order.payment_method in {"PAY_LATER", "COD"}:
        order.is_paid = True

    db.commit()
    db.refresh(order)

    create_notification(
        db,
        order.user_id,
        f"Your order #{order.id} is ready / delivered",
    )
    return order


@router.put("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("USER", "ADMIN")),
):
    order = (
        db.query(models.Order)
        .options(joinedload(models.Order.items).joinedload(models.OrderItem.food))
        .filter(models.Order.id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if current_user.role == "USER":
        if order.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your order")
        if order.status not in {"PLACED", "PAID"}:
            raise HTTPException(
                status_code=400,
                detail="Order cannot be cancelled after preparation",
            )

    validate_transition(order.status, "CANCELLED")
    order.status = "CANCELLED"

    if order.is_paid and order.payment_method == "WALLET":
        user = db.query(models.User).filter(models.User.id == order.user_id).first()
        if user:
            user.wallet_balance += order.total_price or 0
        order.is_paid = False

    for item in order.items:
        food = (
            db.query(models.FoodItem)
            .filter(models.FoodItem.id == item.food_id)
            .with_for_update()
            .first()
        )
        if food:
            food.stock += item.quantity
            create_notification(
                db,
                food.vendor_id,
                f"Order #{order.id} was cancelled",
            )

    db.commit()
    db.refresh(order)

    create_notification(
        db,
        order.user_id,
        f"Your order #{order.id} was cancelled",
    )
    return order


@router.post("/{order_id}/pay", response_model=OrderResponse)
def pay_for_order(
    order_id: int,
    payment_method: PaymentMethod = PaymentMethod.UPI_INAPP,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user=Depends(require_role("USER")),
):
    order = (
        db.query(models.Order)
        .options(joinedload(models.Order.items).joinedload(models.OrderItem.food))
        .filter(
            models.Order.id == order_id,
            models.Order.user_id == current_user.id,
        )
        .first()
    )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if idempotency_key:
        existing_order = (
            db.query(models.Order)
            .options(joinedload(models.Order.items))
            .filter(
                models.Order.idempotency_key == idempotency_key,
                models.Order.user_id == current_user.id,
            )
            .first()
        )
        if existing_order:
            return existing_order

    if order.is_paid or order.status == "PAID":
        return order

    if order.status != "PLACED":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot pay for order in status {order.status}",
        )

    validate_transition(order.status, "PAID")

    if payment_method == PaymentMethod.WALLET:
        if (current_user.wallet_balance or 0) < (order.total_price or 0):
            raise HTTPException(status_code=400, detail="Insufficient wallet balance")
        current_user.wallet_balance -= order.total_price
        order.is_paid = True
        order.status = "PAID"
    elif payment_method in {
        PaymentMethod.UPI_INAPP,
        PaymentMethod.CARD,
    }:
        order.is_paid = True
        order.status = "PAID"
    else:
        # COD / PAY_LATER: confirm order for preparation, collect money later
        order.is_paid = False
        order.status = "PAID"

    order.payment_method = payment_method.value
    if idempotency_key:
        order.idempotency_key = idempotency_key

    if not order.vendor_id:
        order.vendor_id = _vendor_id_for_order(order)

    db.commit()
    db.refresh(order)

    create_notification(
        db,
        current_user.id,
        f"Payment confirmed for order #{order.id}",
    )

    vendor_id = _vendor_id_for_order(order)
    if vendor_id:
        create_notification(
            db,
            vendor_id,
            f"Order #{order.id} has been confirmed/paid",
        )

    return order


@router.post("/checkout")
def checkout(
    request: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("USER")),
):
    cart_items = (
        db.query(models.CartItem)
        .filter(models.CartItem.user_id == current_user.id)
        .all()
    )

    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    first_food = (
        db.query(models.FoodItem)
        .filter(models.FoodItem.id == cart_items[0].food_id)
        .first()
    )
    if not first_food:
        raise HTTPException(status_code=404, detail="Food item not found")

    vendor = (
        db.query(models.User)
        .filter(
            models.User.id == first_food.vendor_id,
            models.User.role == "VENDOR",
        )
        .first()
    )
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if vendor.is_open is False:
        raise HTTPException(status_code=400, detail="Vendor is currently closed")

    if vendor.opening_hour is None or vendor.closing_hour is None:
        raise HTTPException(
            status_code=400,
            detail="Vendor working hours are not configured yet",
        )

    try:
        available_slots = pickup_service.generate_pickup_slots(
            opening_hour=vendor.opening_hour,
            closing_hour=vendor.closing_hour,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        parsed_clock = datetime.strptime(request.pickup_time, "%I:%M %p")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid time format (use HH:MM AM/PM)",
        )

    if available_slots and request.pickup_time not in available_slots:
        raise HTTPException(
            status_code=400,
            detail="Selected pickup time is not available",
        )

    pickup_time = datetime.combine(datetime.now().date(), parsed_clock.time())

    order = models.Order(
        user_id=current_user.id,
        vendor_id=vendor.id,
        status="PLACED",
        total_price=0,
        pickup_time=pickup_time,
    )
    db.add(order)
    db.flush()

    total = 0.0
    for item in cart_items:
        food = (
            db.query(models.FoodItem)
            .filter(models.FoodItem.id == item.food_id)
            .with_for_update()
            .first()
        )
        if not food:
            raise HTTPException(status_code=404, detail="Food not found")

        if food.vendor_id != vendor.id:
            raise HTTPException(
                status_code=400,
                detail="Cart contains items from multiple vendors",
            )

        if not food.is_available:
            raise HTTPException(
                status_code=400,
                detail=f"{food.name} is currently unavailable",
            )

        if food.stock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough stock for {food.name}",
            )

        food.stock -= item.quantity
        db.add(
            models.OrderItem(
                order_id=order.id,
                food_id=food.id,
                quantity=item.quantity,
                price_at_time=food.price,
            )
        )
        total += food.price * item.quantity

    order.total_price = total

    db.query(models.CartItem).filter(
        models.CartItem.user_id == current_user.id
    ).delete()

    db.commit()
    db.refresh(order)

    create_notification(
        db,
        current_user.id,
        f"Your order #{order.id} has been placed successfully",
    )
    create_notification(
        db,
        vendor.id,
        f"New order #{order.id} received",
    )

    return {
        "order_id": order.id,
        "status": order.status,
        "pickup_time": order.pickup_time.isoformat() if order.pickup_time else None,
        "total": total,
    }


@router.put("/vendor/hours")
def update_vendor_hours(
    request: models.VendorHoursUpdate,
    db: Session = Depends(get_db),
    vendor=Depends(require_role("VENDOR")),
):
    if request.closing_hour <= request.opening_hour:
        raise HTTPException(
            status_code=400,
            detail="Closing hour must be greater than opening hour",
        )

    vendor.opening_hour = request.opening_hour
    vendor.closing_hour = request.closing_hour
    db.commit()
    db.refresh(vendor)

    return {
        "message": "Working hours updated successfully",
        "opening_hour": vendor.opening_hour,
        "closing_hour": vendor.closing_hour,
    }


@router.get("/vendors/{vendor_id}/pickup-slots")
def get_vendor_pickup_slots(vendor_id: int, db: Session = Depends(get_db)):
    vendor = (
        db.query(models.User)
        .filter(
            models.User.id == vendor_id,
            models.User.role == "VENDOR",
        )
        .first()
    )

    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if vendor.opening_hour is None or vendor.closing_hour is None:
        return {
            "is_open": False,
            "next_available": None,
            "slots": [],
            "message": "Vendor working hours not configured",
        }

    slots = pickup_service.generate_pickup_slots(
        opening_hour=vendor.opening_hour,
        closing_hour=vendor.closing_hour,
    )

    return {
        "is_open": len(slots) > 0 and (vendor.is_open is not False),
        "next_available": slots[0] if slots else None,
        "slots": slots,
    }


@router.get("/payment-summary", response_model=PaymentSummaryResponse)
def get_payment_summary(
    order_id: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("USER")),
):
    query = db.query(models.Order).filter(
        models.Order.user_id == current_user.id,
        models.Order.status == "PLACED",
    )
    if order_id is not None:
        query = query.filter(models.Order.id == order_id)

    order = query.order_by(models.Order.id.desc()).first()
    if not order:
        raise HTTPException(status_code=400, detail="No pending order found")

    order_items = (
        db.query(models.OrderItem)
        .options(joinedload(models.OrderItem.food))
        .filter(models.OrderItem.order_id == order.id)
        .all()
    )

    items = []
    for item in order_items:
        name = item.food.name if item.food else f"Item #{item.food_id}"
        items.append({
            "name": name,
            "quantity": item.quantity,
            "price": item.price_at_time * item.quantity,
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
        "wallet_balance": current_user.wallet_balance or 0,
        "wallet_enabled": True,
        "upi_enabled": True,
        "card_enabled": True,
    }


@router.get("/{order_id}/confirmation")
def get_order_confirmation(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("USER")),
):
    order = (
        db.query(models.Order)
        .filter(
            models.Order.id == order_id,
            models.Order.user_id == current_user.id,
        )
        .first()
    )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    year = datetime.now().year
    return {
        "order_id": order.id,
        "display_id": f"ORD-{year}-{order.id:06d}",
        "pickup_time": (
            order.pickup_time.strftime("%I:%M %p") if order.pickup_time else "N/A"
        ),
        "pickup_location": "Campus Cafe",
        "counter": "Counter #3",
        "preparation_time": "15-20 minutes",
        "status": order.status,
        "total": order.total_price,
    }


@router.post("/confirm-payment")
def confirm_payment(
    data: ConfirmPaymentRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("USER")),
):
    query = db.query(models.Order).filter(
        models.Order.user_id == current_user.id,
        models.Order.status == "PLACED",
    )
    if data.order_id is not None:
        query = query.filter(models.Order.id == data.order_id)

    order = query.order_by(models.Order.id.desc()).first()
    if not order:
        raise HTTPException(status_code=400, detail="No pending order found")

    item_total = order.total_price or 0
    service_fee = 10.0
    final_total = item_total + service_fee
    method = data.payment_method or PaymentMethod.UPI_INAPP

    if method == PaymentMethod.WALLET:
        if (current_user.wallet_balance or 0) < final_total:
            raise HTTPException(status_code=400, detail="Insufficient wallet balance")
        current_user.wallet_balance -= final_total
        order.is_paid = True
        order.status = "PAID"
    elif method in {PaymentMethod.UPI_INAPP, PaymentMethod.CARD}:
        order.is_paid = True
        order.status = "PAID"
    else:
        order.is_paid = False
        order.status = "PAID"

    order.payment_method = method.value
    if not order.vendor_id:
        order.vendor_id = _vendor_id_for_order(order)

    db.commit()
    db.refresh(order)

    create_notification(
        db,
        current_user.id,
        f"Payment confirmed for order #{order.id}",
    )
    vendor_id = _vendor_id_for_order(order)
    if vendor_id:
        create_notification(
            db,
            vendor_id,
            f"Order #{order.id} has been confirmed/paid",
        )

    return {
        "order_id": order.id,
        "status": order.status,
        "is_paid": order.is_paid,
        "payment_method": order.payment_method,
    }


@router.get("/history", response_model=list[OrderHistoryResponse])
def get_order_history(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("USER")),
):
    orders = (
        db.query(models.Order)
        .options(
            joinedload(models.Order.items)
            .joinedload(models.OrderItem.food)
            .joinedload(models.FoodItem.vendor),
            joinedload(models.Order.vendor),
        )
        .filter(models.Order.user_id == current_user.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )

    order_history = []
    for order in orders:
        items = []
        for item in order.items:
            food_name = item.food.name if item.food else f"Item #{item.food_id}"
            items.append({
                "food_name": food_name,
                "quantity": item.quantity,
                "price_at_time": item.price_at_time,
            })

        vendor_name = "Unknown vendor"
        if order.vendor and (order.vendor.shop_name or order.vendor.name):
            vendor_name = order.vendor.shop_name or order.vendor.name
        elif order.items and order.items[0].food and order.items[0].food.vendor:
            vendor = order.items[0].food.vendor
            vendor_name = vendor.shop_name or vendor.name or "Unknown vendor"

        order_history.append({
            "order_id": order.id,
            "vendor_name": vendor_name,
            "total_items": sum(item.quantity for item in order.items),
            "total_price": order.total_price,
            "status": order.status,
            "pickup_time": order.pickup_time or order.created_at,
            "is_paid": order.is_paid,
            "payment_method": order.payment_method,
            "created_at": order.created_at,
            "items": items,
        })

    return order_history


@router.get("/{order_id}/track")
def track_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("USER", "VENDOR", "ADMIN")),
):
    order = (
        db.query(models.Order)
        .options(joinedload(models.Order.items).joinedload(models.OrderItem.food))
        .filter(models.Order.id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if current_user.role == "USER" and order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your order")

    if current_user.role == "VENDOR" and order.vendor_id != current_user.id:
        vendor_order = (
            db.query(models.Order)
            .join(models.OrderItem)
            .join(models.FoodItem)
            .filter(
                models.Order.id == order_id,
                models.FoodItem.vendor_id == current_user.id,
            )
            .first()
        )
        if not vendor_order:
            raise HTTPException(status_code=403, detail="Not your order")

    year = datetime.now().year
    status = order.status

    return {
        "order_id": order.id,
        "display_id": f"ORD-{year}-{order.id:06d}",
        "status": status,
        "token": order.id + 100000,
        "total": order.total_price,
        "items": [
            {
                "name": item.food.name if item.food else f"Item #{item.food_id}",
                "quantity": item.quantity,
                "price": item.price_at_time,
            }
            for item in order.items
        ],
        "timeline": [
            {
                "title": "Order Placed",
                "time": order.created_at.strftime("%I:%M %p") if order.created_at else "",
                "is_completed": True,
                "is_current": status == "PLACED",
            },
            {
                "title": "Payment Confirmed",
                "time": "",
                "is_completed": status in {"PAID", "PREPARING", "DELIVERED"},
                "is_current": status == "PAID",
            },
            {
                "title": "Preparing",
                "time": "",
                "is_completed": status in {"PREPARING", "DELIVERED"},
                "is_current": status == "PREPARING",
            },
            {
                "title": "Completed",
                "time": "",
                "is_completed": status == "DELIVERED",
                "is_current": status == "DELIVERED",
            },
        ],
    }
