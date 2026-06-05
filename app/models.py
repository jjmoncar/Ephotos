from datetime import datetime
from app import db

class QRSession(db.Model):
    __tablename__ = 'qr_session'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    token = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    event_name = db.Column(db.String(255))
    
    users = db.relationship('User', backref='session', lazy=True)

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey('qr_session.id'))
    full_name = db.Column(db.String(255))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    folder_name = db.Column(db.String(255), nullable=False)
    is_blocked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    files = db.relationship('UploadedFile', backref='user', lazy=True)
    
    __table_args__ = (
        db.UniqueConstraint('session_id', 'email', name='uq_session_email'),
        db.UniqueConstraint('session_id', 'phone', name='uq_session_phone'),
    )

class UploadedFile(db.Model):
    __tablename__ = 'uploaded_file'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    original_name = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    sha256_hash = db.Column(db.String(64), nullable=False)
    drive_file_id = db.Column(db.String(255))
    status = db.Column(db.String(50), default='pending') # pending | success | error
    error_msg = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class AppConfig(db.Model):
    __tablename__ = 'app_config'
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=False)
