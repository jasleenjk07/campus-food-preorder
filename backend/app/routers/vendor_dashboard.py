from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from datetime import datetime

from app.database import get_db
from app import models
from app.auth.roles import require_role

router = APIRouter(tags=["vendor"])

@router.get("/dashboard")
def vendor_dashboard(
    db: Session = Depends(get_db),
    vendor = Depends(require_role("VENDOR"))
):
    today = date.today()

    orders = (
        db.query(models.Order)
        .join(models.OrderItem)
        .join(models.FoodItem)
        .filter(models.FoodItem.vendor_id == vendor.id)
        .all()
    )

    today_orders = [
        o for o in orders if o.created_at.date() == today
    ]

    pending = [o for o in orders if o.status == "PLACED"]
    preparing = [o for o in orders if o.status == "PREPARING"]
    delivered = [o for o in orders if o.status == "DELIVERED"]

    today_revenue = sum(
        o.total_price for o in today_orders if o.is_paid
    )

    return {
        "today_orders": len(today_orders),
        "pending_orders": len(pending),
        "preparing_orders": len(preparing),
        "completed_orders": len(delivered),
        "today_revenue": today_revenue
    }