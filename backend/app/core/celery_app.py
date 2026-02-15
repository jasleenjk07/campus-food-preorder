from celery import Celery

celery_app = Celery(
    "eatsy", #Celery app name
    broker="redis://localhost:6379/0", #message queue system. Redis running on:, Host: localhost, Port: 6379, Database: 0
    backend="redis://localhost:6379/0",
    include=["app.tasks.notifications"]
)

celery_app.autodiscover_tasks(["app.tasks"])

celery_app.conf.task_routes = { #Any task inside app.tasks.notifications should go to the notifications queue.
    "app.tasks.notifications.*": {"queue": "notifications"}
}