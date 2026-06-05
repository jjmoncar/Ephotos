import hashlib
import magic
from werkzeug.utils import secure_filename

ALLOWED_MIME_TYPES = {
    # Imágenes
    "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif",
    # Videos
    "video/mp4", "video/quicktime", "video/x-msvideo", "video/webm",
}

def compute_hash(file_path: str) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def validate_file(file_path: str, max_size_mb: int) -> tuple[bool, str]:
    import os
    size = os.path.getsize(file_path)
    
    if size > max_size_mb * 1024 * 1024:
        return False, f"Archivo demasiado grande ({size / 1e6:.1f} MB)"

    # Verificar MIME real
    mime = magic.from_file(file_path, mime=True)
    if mime not in ALLOWED_MIME_TYPES:
        return False, f"Tipo de archivo no permitido: {mime}"

    return True, "ok"

def sanitize_folder_name(name: str) -> str:
    # simple secure filename, but we want spaces maybe?
    # the PRD says to replace spaces with underscores or just sanitize
    # werkzeug's secure_filename is a good start
    sanitized = secure_filename(name)
    if not sanitized:
        sanitized = "user"
    return sanitized
