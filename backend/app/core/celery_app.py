from celery import Celery

from app.config import settings

celery_app = Celery(
    "cravix",
    broker=settings.REDIS_URL,
    include=["app.tasks.notifications"],
)

# Do not use a Redis result backend — when Redis is down, .delay() was
# retrying for ~20s and blocking API requests (checkout/pay/notifications).
celery_app.conf.update(
    task_ignore_result=True,
    task_store_eager_result=False,
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        "socket_timeout": 2,
        "socket_connect_timeout": 2,
        "max_retries": 1,
    },
    task_routes={
        "app.tasks.notifications.send_notification_task": {"queue": "notifications"},
        "app.tasks.notifications.send_email_notification": {"queue": "notifications"},
    },
)

celery = celery_app
