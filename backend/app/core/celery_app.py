from celery import Celery
from app.config import settings

celery_app = Celery(
    "cravix",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.notifications"],  # Explicitly include tasks
)

celery_app.conf.task_routes = {
    "app.tasks.notifications.send_notification_task": {"queue": "notifications"},
    "app.tasks.notifications.send_email_notification": {"queue": "notifications"},
}

celery = celery_app