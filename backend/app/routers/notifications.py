from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app import models
from app.auth.roles import require_role
from app.schemas import PreferenceUpdateSchema, NotificationResponse
from app.utils import publish_realtime

router = APIRouter(tags=["Notifications"])


def _publish_unread_count(user_id: int, unread_count: int):
    publish_realtime(user_id, f"unread_count:{unread_count}")


@router.get("/me", response_model=list[NotificationResponse])
def get_my_notifications(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("USER", "ADMIN", "VENDOR")),
):
    return (
        db.query(models.Notification)
        .filter(models.Notification.user_id == current_user.id)
        .order_by(models.Notification.created_at.desc())
        .all()
    )


@router.put("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("USER", "ADMIN", "VENDOR")),
):
    notification = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == current_user.id,
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    db.commit()

    unread_count = db.query(func.count(models.Notification.id)).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False,
    ).scalar()

    _publish_unread_count(current_user.id, unread_count)
    db.refresh(notification)

    return {"message": "Notification marked as read", "unread_count": unread_count}


@router.put("/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("USER", "ADMIN", "VENDOR")),
):
    notifications = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False,
    ).all()

    if not notifications:
        return {"message": "No unread notifications", "unread_count": 0}

    for n in notifications:
        n.is_read = True

    db.commit()
    _publish_unread_count(current_user.id, 0)

    return {"message": "All notifications marked as read", "unread_count": 0}


@router.get("/vendor", response_model=list[NotificationResponse])
def get_vendor_notifications(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("VENDOR")),
):
    return (
        db.query(models.Notification)
        .filter(models.Notification.user_id == current_user.id)
        .order_by(models.Notification.created_at.desc())
        .all()
    )


@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("USER", "ADMIN", "VENDOR")),
):
    count = db.query(func.count(models.Notification.id)).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False,
    ).scalar()

    return {"unread_count": count}


@router.put("/preferences")
def update_preferences(
    prefs: PreferenceUpdateSchema,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("USER", "VENDOR", "ADMIN")),
):
    preference = db.query(models.NotificationPreference).filter(
        models.NotificationPreference.user_id == current_user.id
    ).first()

    if not preference:
        preference = models.NotificationPreference(user_id=current_user.id)
        db.add(preference)

    preference.order_enabled = prefs.order_enabled
    preference.vendor_enabled = prefs.vendor_enabled
    db.commit()

    return {"message": "Preferences updated"}
