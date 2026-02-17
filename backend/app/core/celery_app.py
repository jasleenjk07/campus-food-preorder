from celery import Celery
from app.config import settings

celery_app = Celery(
    "eatsy", #Celery app name
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.autodiscover_tasks(["app.tasks"])

celery_app.conf.task_routes = { #Any task inside app.tasks.notifications should go to the notifications queue.
    "app.tasks.notifications.send_notification_task": {"queue": "notifications"}
}