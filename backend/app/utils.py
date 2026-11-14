import json
import logging

import redis
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app import models
from app.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(
    schemes=["bcrypt_sha256"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _get_redis_client():
    return redis.Redis.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=1,
        socket_timeout=1,
    )


def publish_realtime(user_id: int, message: str) -> bool:
    try:
        client = _get_redis_client()
        payload = {
            "type": "notification",
            "user_id": user_id,
            "message": message,
        }
        client.publish("notifications", json.dumps(payload))
        client.close()
        return True
    except Exception as exc:
        logger.warning("Realtime publish failed: %s", exc)
        return False


def create_notification(db: Session, user_id: int, message: str):
    """Persist an in-app notification and best-effort push it.

    Email is only enqueued when Redis (Celery broker) is reachable, so
    order/payment APIs never stall on broker outages.
    """
    preference = db.query(models.NotificationPreference).filter(
        models.NotificationPreference.user_id == user_id
    ).first()

    if preference and not preference.order_enabled:
        return

    notification = models.Notification(
        user_id=user_id,
        message=message,
        is_read=False,
    )
    db.add(notification)
    db.commit()

    redis_ok = publish_realtime(user_id, message)
    if not redis_ok:
        return

    try:
        from app.tasks.notifications import send_email_notification

        send_email_notification.apply_async(
            args=(user_id, "Cravix Notification", message),
            ignore_result=True,
            retry=False,
        )
    except Exception as exc:
        logger.warning("Email notification enqueue failed: %s", exc)
