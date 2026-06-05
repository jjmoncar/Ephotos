import qrcode
import uuid
from datetime import datetime, timedelta
from io import BytesIO

def generate_qr(base_url: str, expiry_hours: int = 24) -> dict:
    token = str(uuid.uuid4())
    expiry = datetime.utcnow() + timedelta(hours=expiry_hours)
    url = f"{base_url}/upload/{token}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0ff0fc", back_color="#0a0a0f")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return {
        "token": token,
        "url": url,
        "expiry": expiry,
        "image_bytes": buffer.read()
    }
