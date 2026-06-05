from celery import Celery
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Ensure the project root is in the Python path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

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
