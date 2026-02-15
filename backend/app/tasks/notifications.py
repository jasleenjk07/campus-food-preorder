from app.core.celery_app import celery_app
from app.database import SessionLocal
from app import models
from app.core.redis_ws import RedisConnectionManager

manager = RedisConnectionManager()

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
        import asyncio
        asyncio.run(manager.publish(user_id, message))

    finally:
        db.close()