from passlib.context import CryptContext #Manages password hashing algorithms

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.core.redis_ws import manager
from app.tasks.notifications import send_notification_task

import asyncio

pwd_context = CryptContext(
    schemes=["bcrypt_sha256"], #This avoids the low-level bcrypt issues and is recommended by Passlib.
    deprecated="auto" #If a hashing algorithm becomes weak in the future, mark it as deprecated automatically.
)

def hash_password(password: str) -> str: #It takes a plain password and return a secure hashed password.
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

async def create_notification( #Creates and saves a notification in the database for a specific user.
    db: Session,
    user_id: int,
    message: str
):
    # Check user preference
    preference = db.query(models.NotificationPreference).filter(
        models.NotificationPreference.user_id == user_id
    ).first()

    # If preferences exist and notifications disabled → stop
    if preference and not preference.order_enabled:
        return

    # Create notification in DB
    notification = models.Notification(
        user_id=user_id,
        message=message,
        is_read=False
    )

    db.add(notification)
    db.commit()

    # Recalculate unread count
    unread_count = db.query(func.count(models.Notification.id)).filter(
        models.Notification.user_id == user_id,
        models.Notification.is_read == False
    ).scalar()

    # Publish to Redis
    await manager.publish(
        user_id,
        {
            "type": "unread_count_update",
            "unread_count": unread_count
        }
    )