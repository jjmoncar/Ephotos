from app import create_app, db
from app.models import AppConfig

def init_db():
    app = create_app()
    with app.app_context():
        default_config = {
            'max_photos_per_user': '20',
            'max_videos_per_user': '5',
            'max_photo_size_mb': '50',
            'max_video_size_mb': '500',
            'qr_expiry_hours': '24',
            'required_fields': 'name,email',
            'drive_root_folder_id': '',
            'app_language': 'es'
        }
        
        for key, value in default_config.items():
            existing = AppConfig.query.get(key)
            if not existing:
                config_item = AppConfig(key=key, value=value)
                db.session.add(config_item)
        
        db.session.commit()
        print("Database initialized with default configurations.")

if __name__ == "__main__":
    init_db()
