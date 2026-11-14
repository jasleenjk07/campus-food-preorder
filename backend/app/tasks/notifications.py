import json
import logging

import redis

from app.core.celery_app import celery_app
from app.database import SessionLocal
from app import models
from app.config import settings
from app.core.email import send_email

logger = logging.getLogger(__name__)


def _get_redis():
    return redis.Redis.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


@celery_app.task
def send_notification_task(user_id: int, message: str):
    payload = {
        "type": "notification",
        "user_id": user_id,
        "message": message,
    }
    client = _get_redis()
    try:
        client.publish("notifications", json.dumps(payload))
    finally:
        client.close()


@celery_app.task
def send_email_notification(user_id: int, subject: str, message: str):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user and user.email and settings.EMAIL_USER and settings.EMAIL_PASSWORD:
            send_email(user.email, subject, message)
    except Exception as exc:
        logger.warning("Email send failed: %s", exc)
    finally:
        db.close()
