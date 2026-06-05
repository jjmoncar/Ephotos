from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

def make_celery(app_name=__name__):
    broker = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    
    celery = Celery(
        app_name,
        backend=backend,
        broker=broker,
        include=['app.tasks.upload_task']
    )
    return celery

celery = make_celery()

if __name__ == '__main__':
    celery.start()
