import redis
import json

from app.core.celery_app import celery_app
from app.database import SessionLocal
from app import models
from app.config import settings
from app.core.email import send_email
from app.core.celery_app import celery_app

r = redis.Redis.from_url(settings.REDIS_URL) #connects Celery to Redis

@celery_app.task
def send_notification_task(user_id: int, message: str):
    payload = {
        "type": "notification",
        "user_id": user_id,
        "message": message
    }

    r.publish("notifications", json.dumps(payload))

@celery_app.task
def send_email_notification(user_id: int, subject: str, message: str): #Runs in the background using Celery
    db = SessionLocal()
    user = db.query(models.User).filter(models.User.id == user_id).first()

    if user:
        send_email(user.email, subject, message) #user.email = Recipient (your Cravix user)

    db.close()