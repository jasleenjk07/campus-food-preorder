from app.core.celery_app import celery_app
from app.database import SessionLocal
from app import models
import redis

@celery_app.task
def send_notification_task(user_id: int, message: str):
    db = SessionLocal()

    try:
        notification = models.Notification(
            user_id=user_id,
            message=message
        )
        db.add(notification)
        db.commit()

        #Publish to Redis WebSocket
        redis_client = redis.Redis(host="localhost", port=6379, db=0)
        redis_client.publish(f"user:{user_id}", message)

    finally:
        db.close()