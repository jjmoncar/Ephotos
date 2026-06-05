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

@bp.route('/qr/generate', methods=['POST'])
@require_admin_auth
def qr_generate():
    # Deactivate current
    QRSession.query.filter_by(is_active=True).update({'is_active': False})
    
    config = get_config()
    expiry_hours = int(config.get('qr_expiry_hours', 24))
    base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
    
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
    session["oauth_state"] = state
    return redirect(auth_url)

# This needs to be in a non-prefixed route or we use /admin/oauth2callback
# But PRD says @app.route("/oauth2callback")
@bp.route('/oauth2callback')
@require_admin_auth
def oauth2callback():
    flow = get_oauth2_flow()
    # Need to pass the full URL to fetch_token
    # If reverse proxy, might need to ensure url scheme is https
    authorization_response = request.url.replace('http://', 'https://') if os.getenv('FLASK_ENV') == 'production' else request.url
    flow.fetch_token(authorization_response=authorization_response)
    creds = flow.credentials
    token_file = os.getenv("GOOGLE_OAUTH2_TOKEN_FILE", "credentials/oauth2_token.json")
    with open(token_file, "w") as f:
        f.write(creds.to_json())
    flash('Google Drive autorizado correctamente.', 'success')
    return redirect(url_for('admin.dashboard'))
