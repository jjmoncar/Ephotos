import os
import magic
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session, current_app
from werkzeug.utils import secure_filename
from app import db, limiter
from app.models import QRSession, User, UploadedFile, AppConfig
from app.services.file_utils import compute_hash, validate_file, sanitize_folder_name
from app.tasks.upload_task import upload_to_drive

bp = Blueprint('upload', __name__)

def get_config():
    configs = AppConfig.query.all()
    return {c.key: c.value for c in configs}

@bp.route('/upload/<token>', methods=['GET'])
def view_upload(token):
    qr_session = QRSession.query.filter_by(token=token, is_active=True).first()
    if not qr_session:
        return render_template('expired.html', message="El código QR es inválido o ha sido desactivado.")
        
    if qr_session.expires_at and datetime.utcnow() > qr_session.expires_at:
        return render_template('expired.html', message="El código QR ha expirado.")

    user_id = session.get(f'user_id_{token}')
    if user_id:
        user = User.query.get(user_id)
        if user:
            if user.is_blocked:
                return render_template('expired.html', message="Tu acceso ha sido restringido.")
            return render_template('upload.html', token=token, user=user)

    return render_template('register.html', token=token)

@bp.route('/register/<token>', methods=['POST'])
@limiter.limit("5/hour")
def register(token):
    qr_session = QRSession.query.filter_by(token=token, is_active=True).first()
    if not qr_session or (qr_session.expires_at and datetime.utcnow() > qr_session.expires_at):
        return jsonify({"error": "Sesión inválida o expirada"}), 400

    data = request.form
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()

    if not full_name:
        return jsonify({"error": "El nombre es obligatorio"}), 400

    # Find existing user in this session by email or phone
    user = None
    if email:
        user = User.query.filter_by(session_id=qr_session.id, email=email).first()
    if not user and phone:
        user = User.query.filter_by(session_id=qr_session.id, phone=phone).first()
        
    if not user:
        folder_name = sanitize_folder_name(full_name)
        if email:
            folder_name += f"_({email})"
        elif phone:
            folder_name += f"_({phone})"
            
        user = User(
            session_id=qr_session.id,
            full_name=full_name,
            email=email,
            phone=phone,
            folder_name=folder_name
        )
        db.session.add(user)
        db.session.commit()

    if user.is_blocked:
        return jsonify({"error": "Tu acceso ha sido restringido"}), 403

    session[f'user_id_{token}'] = user.id
    return redirect(url_for('upload.view_upload', token=token))

@bp.route('/api/upload/<token>', methods=['POST'])
@limiter.limit("20/minute")
def do_upload(token):
    user_id = session.get(f'user_id_{token}')
    if not user_id:
        return jsonify({"error": "No registrado"}), 401
        
    user = User.query.get(user_id)
    if not user or user.is_blocked:
        return jsonify({"error": "Usuario inválido o bloqueado"}), 403

    if 'file' not in request.files:
        return jsonify({"error": "No se envió archivo"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Archivo sin nombre"}), 400

    config = get_config()
    max_photo_mb = int(config.get('max_photo_size_mb', 50))
    max_video_mb = int(config.get('max_video_size_mb', 500))
    
    # Save file temporarily to analyze
    tmp_dir = os.path.join(current_app.root_path, '..', 'tmp', 'uploads')
    os.makedirs(tmp_dir, exist_ok=True)
    
    # secure random filename for tmp
    import uuid
    tmp_path = os.path.join(tmp_dir, f"{uuid.uuid4()}_{secure_filename(file.filename)}")
    file.save(tmp_path)
    
    # Check mime type to determine if photo or video
    mime = magic.from_file(tmp_path, mime=True)
    is_video = mime.startswith('video/')
    max_mb = max_video_mb if is_video else max_photo_mb
    
    is_valid, msg = validate_file(tmp_path, max_mb)
    if not is_valid:
        os.remove(tmp_path)
        return jsonify({"error": msg}), 400
        
    # Deduplication
    file_hash = compute_hash(tmp_path)
    existing_file = UploadedFile.query.filter_by(user_id=user.id, sha256_hash=file_hash).first()
    if existing_file:
        os.remove(tmp_path)
        return jsonify({"error": "Ya enviaste este archivo"}), 400
        
    # Check limits
    photos_count = UploadedFile.query.filter(UploadedFile.user_id == user.id, UploadedFile.mime_type.like('image/%')).count()
    videos_count = UploadedFile.query.filter(UploadedFile.user_id == user.id, UploadedFile.mime_type.like('video/%')).count()
    
    if is_video and videos_count >= int(config.get('max_videos_per_user', 5)):
        os.remove(tmp_path)
        return jsonify({"error": "Límite de videos alcanzado"}), 400
    if not is_video and photos_count >= int(config.get('max_photos_per_user', 20)):
        os.remove(tmp_path)
        return jsonify({"error": "Límite de fotos alcanzado"}), 400

    file_size = os.path.getsize(tmp_path)
    
    # Save to db
    upload_record = UploadedFile(
        user_id=user.id,
        original_name=file.filename,
        mime_type=mime,
        file_size=file_size,
        sha256_hash=file_hash,
        status='pending'
    )
    db.session.add(upload_record)
    db.session.commit()
    
    # Queue task
    upload_to_drive.delay(tmp_path, user.id, file.filename, upload_record.id)
    
    return jsonify({"message": "Archivo en cola para subida", "id": upload_record.id}), 200

@bp.route('/api/status/<int:file_id>', methods=['GET'])
def check_status(file_id):
    file_record = UploadedFile.query.get_or_404(file_id)
    return jsonify({"status": file_record.status, "error_msg": file_record.error_msg})
