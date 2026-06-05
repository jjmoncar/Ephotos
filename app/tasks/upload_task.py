import os
from celery_app import celery
from app import create_app, db
from app.models import UploadedFile, User, AppConfig
from app.services.drive import get_drive_service, get_or_create_folder, upload_file

@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def upload_to_drive(self, file_path: str, user_id: int, original_name: str, file_id: int):
    app = create_app()
    with app.app_context():
        file_record = UploadedFile.query.get(file_id)
        if not file_record:
            if os.path.exists(file_path):
                os.remove(file_path)
            return
            
        try:
            service = get_drive_service()
            user = User.query.get(user_id)
            
            root_folder_config = AppConfig.query.get('drive_root_folder_id')
            root_folder_id = root_folder_config.value if root_folder_config else ""
            
            # Use root as parent if not specified
            parent_id = root_folder_id if root_folder_id else "root"
            
            folder_id = get_or_create_folder(service, user.folder_name, parent_id)
            drive_file_id = upload_file(service, file_path, original_name, folder_id)
            
            file_record.drive_file_id = drive_file_id
            file_record.status = "success"
            db.session.commit()
            
        except Exception as exc:
            file_record.status = "error"
            file_record.error_msg = str(exc)
            db.session.commit()
            raise self.retry(exc=exc)
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
