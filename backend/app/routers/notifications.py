import asyncio

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app import models
from app.auth.roles import require_role
from app.core.redis_ws import manager

router = APIRouter(tags=["Notifications"])


@router.get("/me")
def get_my_notifications(
    db: Session = Depends(get_db),
    current_user = Depends(require_role("USER", "ADMIN", "VENDOR"))
):
    return (
        db.query(models.Notification)
        .filter(models.Notification.user_id == current_user.id)
        .order_by(models.Notification.created_at.desc())
        .all()
    )

@router.put("/{notification_id}/read") # Marks one specific notification as read.
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_role("USER", "ADMIN", "VENDOR"))
):
    notification = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == current_user.id
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    db.commit()

    unread_count = db.query(func.count(models.Notification.id)).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False
    ).scalar()

    asyncio.create_task(
        manager.publish(
            current_user.id,
            {
                "type": "unread_count_update",
                "unread_count": unread_count
            }
        )
    )

    db.refresh(notification)

    return {"message": "Notification marked as read"}

@router.put("/read-all") # Marks all unread notifications as read.
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user = Depends(require_role("USER", "ADMIN", "VENDOR"))
):
    # Get all unread notifications for current user
    notifications = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False
    ).all()

    # If no unread notifications
    if not notifications:
        return {"message": "No unread notifications"}

    # Mark each as read
    for n in notifications:
        n.is_read = True

    # Save changes
    db.commit()

    asyncio.create_task(
        manager.publish(
            current_user.id,
            {
                "type": "unread_count_update",
                "unread_count": 0
            }
        )
    )

    return {"message": "All notifications marked as read"}

@router.get("/vendor")
def get_vendor_notifications(
    db: Session = Depends(get_db),
    current_user = Depends(require_role("VENDOR"))
):
    return (
        db.query(models.Notification)
        .filter(models.Notification.user_id == current_user.id)
        .order_by(models.Notification.created_at.desc()) # Sorts notifications by creation date in descending order.
        .all()
    )

# Gets the number of unread notifications for the current user.
@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user = Depends(require_role("USER", "ADMIN", "VENDOR"))
):
    count = db.query(func.count(models.Notification.id)).filter( #func.count() = SQL COUNT(*)
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False
    ).scalar() #scalar() = returns the result as a single value (int, float, string, etc.)

    return {
        "unread_count": count
    }

## FOR TESTING PURPOSES ONLY
# @router.get("/test")
# async def test_notification(
#     db: Session = Depends(get_db),
#     current_user = Depends(require_role("USER", "ADMIN", "VENDOR"))
# ):
#     await manager.publish(
#         current_user.id,
#         {
#             "type": "unread_count_update",
#             "unread_count": 999
#         }
#     )

#     return {"message": "Test sent"}