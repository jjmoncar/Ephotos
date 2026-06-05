import os
from functools import wraps
from flask import Blueprint, render_template, request, Response, redirect, url_for, flash, current_app, session
from app import db
from app.models import QRSession, AppConfig, User, UploadedFile
from app.services.qr_generator import generate_qr
from app.services.drive import get_oauth2_flow

bp = Blueprint('admin', __name__, url_prefix='/admin')

def check_credentials(username, password):
    admin_user = current_app.config.get('ADMIN_USERNAME', 'admin')
    admin_pass = current_app.config.get('ADMIN_PASSWORD', 'admin')
    return username == admin_user and password == admin_pass

def require_admin_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_credentials(auth.username, auth.password):
            return Response(
                "Acceso denegado", 401,
                {"WWW-Authenticate": 'Basic realm="Admin Panel"'}
            )
        return f(*args, **kwargs)
    return decorated

def get_config():
    configs = AppConfig.query.all()
    return {c.key: c.value for c in configs}

@bp.route('/')
@require_admin_auth
def dashboard():
    total_users = User.query.count()
    total_photos = UploadedFile.query.filter(UploadedFile.mime_type.like('image/%')).count()
    total_videos = UploadedFile.query.filter(UploadedFile.mime_type.like('video/%')).count()
    
    # size in mb
    total_bytes = db.session.query(db.func.sum(UploadedFile.file_size)).scalar() or 0
    total_mb = round(total_bytes / (1024 * 1024), 2)
    
    recent_uploads = UploadedFile.query.order_by(UploadedFile.uploaded_at.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html', 
                           total_users=total_users, 
                           total_photos=total_photos,
                           total_videos=total_videos,
                           total_mb=total_mb,
                           recent_uploads=recent_uploads)

@bp.route('/settings', methods=['GET', 'POST'])
@require_admin_auth
def settings():
    if request.method == 'POST':
        for key, value in request.form.items():
            config_item = AppConfig.query.get(key)
            if config_item:
                config_item.value = value
            else:
                db.session.add(AppConfig(key=key, value=value))
        db.session.commit()
        flash('Configuración guardada exitosamente.', 'success')
        return redirect(url_for('admin.settings'))
        
    config = get_config()
    return render_template('admin/settings.html', config=config)

@bp.route('/qr', methods=['GET'])
@require_admin_auth
def qr_view():
    active_session = QRSession.query.filter_by(is_active=True).first()
    return render_template('admin/qr.html', qr_session=active_session)

def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

@bp.route('/qr/generate', methods=['POST'])
@require_admin_auth
def qr_generate():
    # Deactivate current
    QRSession.query.filter_by(is_active=True).update({'is_active': False})
    
    config = get_config()
    expiry_hours = int(config.get('qr_expiry_hours', 24))
    base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
    
    # Dynamically detect and replace localhost/127.0.0.1 with local network IP for mobile convenience
    if "localhost" in base_url or "127.0.0.1" in base_url:
        local_ip = get_local_ip()
        base_url = base_url.replace("localhost", local_ip).replace("127.0.0.1", local_ip)
        current_app.logger.info(f"QR generated using dynamic local network IP: {base_url}")
        
    qr_data = generate_qr(base_url, expiry_hours)
    
    import base64
    img_b64 = base64.b64encode(qr_data['image_bytes']).decode('utf-8')
    
    # Save the QR session but not the image itself, maybe save token
    new_session = QRSession(
        token=qr_data['token'],
        expires_at=qr_data['expiry'],
        is_active=True
    )
    db.session.add(new_session)
    db.session.commit()
    
    session['last_qr_img'] = img_b64
    flash('Código QR generado exitosamente.', 'success')
    return redirect(url_for('admin.qr_view'))

@bp.route('/participants')
@require_admin_auth
def participants():
    users = User.query.all()
    return render_template('admin/participants.html', users=users)

@bp.route('/participants/<int:id>/block', methods=['POST'])
@require_admin_auth
def block_participant(id):
    user = User.query.get_or_404(id)
    user.is_blocked = not user.is_blocked
    db.session.commit()
    status = "bloqueado" if user.is_blocked else "desbloqueado"
    flash(f'Usuario {user.full_name} ha sido {status}.', 'success')
    return redirect(url_for('admin.participants'))

@bp.route('/history')
@require_admin_auth
def history():
    uploads = UploadedFile.query.order_by(UploadedFile.uploaded_at.desc()).all()
    return render_template('admin/history.html', uploads=uploads)

@bp.route('/authorize')
@require_admin_auth
def authorize():
    flow = get_oauth2_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    
    # Save the state and code_verifier mapping in the DB config table
    state_key = f"oauth_verifier_{state}"
    if hasattr(flow, 'code_verifier') and flow.code_verifier:
        config_item = AppConfig.query.get(state_key)
        if config_item:
            config_item.value = flow.code_verifier
        else:
            db.session.add(AppConfig(key=state_key, value=flow.code_verifier))
        db.session.commit()
        current_app.logger.info(f"[AUTH] Saved state={state} and code_verifier={flow.code_verifier} to AppConfig DB.")
    else:
        current_app.logger.info(f"[AUTH] Flow has no code_verifier! Saved state={state} only.")
        
    return redirect(auth_url)

@bp.route('/oauth2callback')
@require_admin_auth
def oauth2callback():
    state = request.args.get('state')
    state_key = f"oauth_verifier_{state}"
    
    # Retrieve code_verifier from AppConfig DB
    config_item = AppConfig.query.get(state_key)
    code_verifier = config_item.value if config_item else None
    
    current_app.logger.info(f"[CALLBACK] Retrieved state={state} and code_verifier={code_verifier} from AppConfig DB.")
    
    # Delete the temporary verifier from DB
    if config_item:
        try:
            db.session.delete(config_item)
            db.session.commit()
            current_app.logger.info(f"[CALLBACK] Cleaned up state key {state_key} from AppConfig DB.")
        except Exception as e:
            current_app.logger.error(f"[CALLBACK] Failed to delete state key {state_key}: {e}")
            db.session.rollback()

    flow = get_oauth2_flow(state=state)
    if code_verifier:
        flow.code_verifier = code_verifier
        
    kwargs = {}
    if code_verifier:
        kwargs['code_verifier'] = code_verifier
        
    authorization_response = request.url.replace('http://', 'https://') if os.getenv('FLASK_ENV') == 'production' else request.url
    current_app.logger.info(f"[CALLBACK] Exchanging code with kwargs={kwargs} and auth_response={authorization_response}")
    flow.fetch_token(authorization_response=authorization_response, **kwargs)
    
    creds = flow.credentials
    token_file = os.getenv("GOOGLE_OAUTH2_TOKEN_FILE", "credentials/oauth2_token.json")
    with open(token_file, "w") as f:
        f.write(creds.to_json())
    flash('Google Drive autorizado correctamente.', 'success')
    return redirect(url_for('admin.dashboard'))

@bp.route('/upload/<int:id>/retry', methods=['POST'])
@require_admin_auth
def retry_upload(id):
    from app.tasks.upload_task import upload_to_drive
    from werkzeug.utils import secure_filename
    
    file_record = UploadedFile.query.get_or_404(id)
    
    # Try to find the local file
    tmp_dir = os.path.join(current_app.root_path, '..', 'tmp', 'uploads')
    sec_name = secure_filename(file_record.original_name)
    file_path = None
    if os.path.exists(tmp_dir):
        for filename in os.listdir(tmp_dir):
            if filename.endswith(f"_{sec_name}"):
                file_path = os.path.join(tmp_dir, filename)
                break
                
    if not file_path or not os.path.exists(file_path):
        flash(f'El archivo temporal para "{file_record.original_name}" ya no existe en el servidor.', 'error')
        if file_record.status == 'pending':
            file_record.status = 'error'
            file_record.error_msg = 'Archivo temporal perdido en el servidor.'
            db.session.commit()
        return redirect(request.referrer or url_for('admin.dashboard'))
        
    # Queue task again
    file_record.status = 'pending'
    file_record.error_msg = None
    db.session.commit()
    
    upload_to_drive.delay(file_path, file_record.user_id, file_record.original_name, file_record.id)
    flash(f'Reintento de subida encolado para "{file_record.original_name}".', 'success')
    return redirect(request.referrer or url_for('admin.dashboard'))

@bp.route('/upload/retry-all', methods=['POST'])
@require_admin_auth
def retry_all_uploads():
    from app.tasks.upload_task import upload_to_drive
    from werkzeug.utils import secure_filename
    
    failed_or_pending = UploadedFile.query.filter(UploadedFile.status != 'success').all()
    tmp_dir = os.path.join(current_app.root_path, '..', 'tmp', 'uploads')
    
    if not failed_or_pending:
        flash('No hay subidas pendientes o fallidas para reintentar.', 'info')
        return redirect(request.referrer or url_for('admin.dashboard'))
        
    count = 0
    lost_count = 0
    for file_record in failed_or_pending:
        sec_name = secure_filename(file_record.original_name)
        file_path = None
        if os.path.exists(tmp_dir):
            for filename in os.listdir(tmp_dir):
                if filename.endswith(f"_{sec_name}"):
                    file_path = os.path.join(tmp_dir, filename)
                    break
                    
        if file_path and os.path.exists(file_path):
            file_record.status = 'pending'
            file_record.error_msg = None
            db.session.commit()
            upload_to_drive.delay(file_path, file_record.user_id, file_record.original_name, file_record.id)
            count += 1
        else:
            lost_count += 1
            if file_record.status == 'pending':
                file_record.status = 'error'
                file_record.error_msg = 'Archivo temporal perdido en el servidor.'
                db.session.commit()
                
    if count > 0:
        flash(f'Se han encolado {count} archivos para reintentar la subida.', 'success')
    if lost_count > 0:
        flash(f'{lost_count} archivos no pudieron ser reintentados porque su archivo temporal ya no existe.', 'warning')
        
    return redirect(request.referrer or url_for('admin.dashboard'))
