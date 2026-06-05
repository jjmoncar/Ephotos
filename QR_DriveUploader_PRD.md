# QR Drive Uploader — Documento de Requerimientos del Producto (PRD)

> App web que genera un código QR para que personas envíen fotos y videos directamente a Google Drive, organizados automáticamente por usuario.

---

## Tabla de Contenidos

1. [Descripción General](#1-descripción-general)
2. [Stack Tecnológico](#2-stack-tecnológico)
3. [Arquitectura del Sistema](#3-arquitectura-del-sistema)
4. [Módulos y Funcionalidades](#4-módulos-y-funcionalidades)
   - 4.1 [Generación del Código QR](#41-generación-del-código-qr)
   - 4.2 [Registro e Identificación del Usuario](#42-registro-e-identificación-del-usuario)
   - 4.3 [Subida de Archivos](#43-subida-de-archivos)
   - 4.4 [Organización en Google Drive](#44-organización-en-google-drive)
   - 4.5 [Deduplicación de Archivos](#45-deduplicación-de-archivos)
   - 4.6 [Panel de Administración](#46-panel-de-administración)
   - 4.7 [Cola de Tareas Asíncrona](#47-cola-de-tareas-asíncrona)
5. [Base de Datos (SQLite)](#5-base-de-datos-sqlite)
6. [Integración con Google Drive](#6-integración-con-google-drive)
   - 6.1 [Opción A — Service Account](#61-opción-a--service-account)
   - 6.2 [Opción B — OAuth2 (cuenta personal)](#62-opción-b--oauth2-cuenta-personal)
   - 6.3 [Comparación entre opciones](#63-comparación-entre-opciones)
7. [Seguridad y Control de Acceso](#7-seguridad-y-control-de-acceso)
8. [Experiencia de Usuario (UX/UI)](#8-experiencia-de-usuario-uxui)
9. [Diseño Visual — Estilo WEB3 Responsive](#9-diseño-visual--estilo-web3-responsive)
10. [Configuración del Entorno](#10-configuración-del-entorno)
11. [Estructura de Directorios del Proyecto](#11-estructura-de-directorios-del-proyecto)
12. [Variables de Entorno (.env)](#12-variables-de-entorno-env)
13. [Flujo Completo de la Aplicación](#13-flujo-completo-de-la-aplicación)
14. [Endpoints de la API Flask](#14-endpoints-de-la-api-flask)
15. [Instalación y Puesta en Marcha](#15-instalación-y-puesta-en-marcha)
16. [Logging y Monitoreo](#16-logging-y-monitoreo)
17. [Consideraciones de Escalabilidad](#17-consideraciones-de-escalabilidad)
18. [Roadmap de Mejoras Futuras](#18-roadmap-de-mejoras-futuras)

---

## 1. Descripción General

**QR Drive Uploader** es una aplicación web diseñada para eventos, fotógrafos, bodas, conferencias o cualquier ocasión donde el organizador necesite recolectar fotos y videos de múltiples personas de forma ordenada y sin fricción.

### Flujo principal en 3 pasos

```
[Organizador genera QR]  →  [Asistente escanea QR]  →  [Fotos/videos van a Drive organizado]
```

### Características clave

| Característica | Descripción |
|---|---|
| QR dinámico | Enlace con token de sesión y tiempo de expiración configurable |
| Carpetas automáticas | Cada persona tiene su propia carpeta en Google Drive |
| Deduplicación | Hash MD5/SHA256 evita que se suban archivos repetidos |
| Límites configurables | Máximo de fotos, videos y tamaño por archivo, definido por el admin |
| Panel de administración | Dashboard con estadísticas, control de acceso y gestión del QR |
| Subida asíncrona | Cola Celery + Redis para archivos pesados sin timeouts |
| Multiidioma | Soporte español e inglés desde el inicio |

---

## 2. Stack Tecnológico

### Backend

| Componente | Tecnología | Versión recomendada |
|---|---|---|
| Lenguaje | Python | 3.11+ |
| Framework web | Flask | 3.x |
| ORM / Base de datos | SQLite + SQLAlchemy | SQLAlchemy 2.x |
| Migraciones | Flask-Migrate (Alembic) | 4.x |
| Cola de tareas | Celery | 5.x |
| Broker de mensajes | Redis | 7.x |
| Generación de QR | `qrcode[pil]` | 7.x |
| Integración Google Drive | `google-api-python-client` | 2.x |
| Autenticación OAuth2 | `google-auth-oauthlib` | 1.x |
| Hashing de archivos | `hashlib` (stdlib) | — |
| Rate limiting | `Flask-Limiter` | 3.x |
| Variables de entorno | `python-dotenv` | 1.x |
| Validación MIME | `python-magic` | 0.4.x |

### Frontend

| Componente | Tecnología |
|---|---|
| Templating | Jinja2 (incluido en Flask) |
| Estilos | CSS3 custom + variables WEB3 |
| Fuentes | Google Fonts (Syne + Space Mono) |
| Íconos | Heroicons SVG inline |
| Barra de progreso | Fetch API + `ReadableStream` |
| Responsive | CSS Grid + Flexbox (mobile-first) |

---

## 3. Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENTE (Celular)                    │
│  Escanea QR → Abre URL en browser → Sube fotos/videos       │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTPS
┌──────────────────────▼──────────────────────────────────────┐
│                    FLASK APP (servidor)                      │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  Rutas/API  │  │  Auth/Session│  │  Rate Limiter     │  │
│  └──────┬──────┘  └──────────────┘  └───────────────────┘  │
│         │                                                   │
│  ┌──────▼──────────────────────────────────────────────┐   │
│  │              Lógica de negocio                      │   │
│  │  - Validar token QR    - Verificar duplicados       │   │
│  │  - Controlar límites   - Hashear archivos           │   │
│  └──────┬──────────────────────────────────────────────┘   │
│         │                                                   │
│  ┌──────▼──────┐          ┌──────────────────────────────┐ │
│  │   SQLite    │          │  Cola Celery + Redis          │ │
│  │  (SQLAlch.) │          │  - Worker sube a Drive        │ │
│  └─────────────┘          │  - Notifica resultado         │ │
│                           └──────────────┬───────────────┘ │
└──────────────────────────────────────────┼─────────────────┘
                                           │ Google Drive API
                          ┌────────────────▼───────────────┐
                          │         GOOGLE DRIVE            │
                          │  /Evento_2025/                  │
                          │    ├── Juan_Pérez/              │
                          │    │     ├── foto1.jpg          │
                          │    │     └── video1.mp4         │
                          │    └── María_García/            │
                          │          └── foto1.jpg          │
                          └────────────────────────────────┘
```

---

## 4. Módulos y Funcionalidades

### 4.1 Generación del Código QR

El organizador accede al panel de administración y genera un QR que contiene una URL con token único de sesión.

#### Comportamiento

- El QR apunta a: `https://tu-dominio.com/upload/<session_token>`
- El `session_token` es un UUID4 aleatorio almacenado en la base de datos.
- El propietario configura la **expiración del QR** (1h, 8h, 24h, 7 días, sin límite).
- El QR puede ser **regenerado** desde el panel, invalidando automáticamente el anterior.
- El QR se puede descargar como PNG o SVG para imprimir o proyectar.

#### Código de ejemplo — generación del QR

```python
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
```

---

### 4.2 Registro e Identificación del Usuario

Al escanear el QR, el usuario llega a una página de registro simple donde proporciona su identidad. Esta información se usa como nombre de su carpeta en Google Drive.

#### Campos de identificación (el admin elige cuáles activar)

| Campo | Tipo | Validación |
|---|---|---|
| Nombre completo | Texto | Requerido, 3–80 caracteres |
| Correo electrónico | Email | Formato válido, único por sesión |
| Número de celular | Tel | Formato internacional E.164 |

#### Lógica de unicidad

- Si el email o teléfono ya existe en la sesión activa → se muestra el historial de envíos previos y se permite continuar o agregar más archivos (respetando el límite).
- Si el usuario ya alcanzó el límite configurado → se muestra mensaje de "cupo completado" y se bloquea el formulario de subida.

---

### 4.3 Subida de Archivos

#### Tipos de archivo permitidos

```python
ALLOWED_MIME_TYPES = {
    # Imágenes
    "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif",
    # Videos
    "video/mp4", "video/quicktime", "video/x-msvideo", "video/webm",
}
```

#### Validaciones antes de aceptar un archivo

1. **Validación de MIME real** — usando `python-magic` (no solo la extensión del nombre).
2. **Tamaño máximo por archivo** — configurable por el admin (default: 100MB por foto, 500MB por video).
3. **Cantidad máxima** — se verifica contra los límites configurados en la sesión.
4. **Deduplicación por hash** — ver sección 4.5.

#### Proceso de subida

```
Usuario selecciona archivos
        ↓
Validación client-side (tamaño, tipo)
        ↓
POST /upload/<token> con multipart/form-data
        ↓
Flask valida: token activo, límites, MIME real, hash
        ↓
Archivo temporal guardado en /tmp/uploads/
        ↓
Tarea Celery encolada → respuesta inmediata al cliente
        ↓
Worker sube a Google Drive en segundo plano
        ↓
SQLite actualizado con resultado (éxito/error)
        ↓
Cliente consulta estado por SSE o polling
```

---

### 4.4 Organización en Google Drive

Estructura de carpetas creada automáticamente:

```
Google Drive (raíz del evento)
└── [Nombre del Evento] (carpeta raíz configurable)
    ├── [Nombre o Email del Usuario 1]/
    │     ├── foto_001.jpg
    │     ├── foto_002.png
    │     └── video_001.mp4
    └── [Nombre o Email del Usuario 2]/
          └── foto_001.jpg
```

#### Nomenclatura de carpetas

- Se sanitizan caracteres especiales del nombre/email para que sean válidos como nombre de carpeta.
- Si dos personas tienen el mismo nombre, se agrega el email o teléfono como sufijo: `Juan_Pérez_(juan@mail.com)`.

#### Código de ejemplo — crear carpeta en Drive

```python
def get_or_create_folder(service, folder_name: str, parent_id: str) -> str:
    """Retorna el ID de la carpeta, creándola si no existe."""
    query = (
        f"name='{folder_name}' and "
        f"'{parent_id}' in parents and "
        f"mimeType='application/vnd.google-apps.folder' and "
        f"trashed=false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]
```

---

### 4.5 Deduplicación de Archivos

Para evitar que el mismo archivo se suba más de una vez (aunque cambie el nombre), se calcula el hash SHA-256 de cada archivo antes de subirlo.

#### Lógica de deduplicación

```python
import hashlib

def compute_hash(file_stream) -> str:
    sha256 = hashlib.sha256()
    for chunk in iter(lambda: file_stream.read(8192), b""):
        sha256.update(chunk)
    file_stream.seek(0)
    return sha256.hexdigest()
```

#### Reglas de negocio

| Escenario | Comportamiento |
|---|---|
| Mismo archivo, misma persona | Rechazado con mensaje "ya enviaste este archivo" |
| Mismo archivo, otra persona | Permitido (cada persona tiene su propia carpeta) |
| Archivo diferente, mismo nombre | Permitido (se verifica por hash, no por nombre) |

---

### 4.6 Panel de Administración

Accesible en `/admin` con autenticación básica (usuario/contraseña en `.env`).

#### Secciones del panel

**Dashboard — Estadísticas en tiempo real**

- Total de personas que han enviado archivos
- Total de fotos recibidas / Total de videos recibidos
- Espacio total utilizado (MB/GB)
- Últimas subidas (feed en tiempo real)
- Gráfico de actividad por hora

**Configuración del QR**

- Tiempo de expiración del QR
- Regenerar QR (invalida el anterior)
- Descargar QR como PNG
- Habilitar/deshabilitar recepción de archivos

**Configuración de límites**

- Máximo de fotos por persona
- Máximo de videos por persona
- Tamaño máximo por foto (MB)
- Tamaño máximo por video (MB)
- Campos de identificación requeridos (nombre / email / teléfono)
- Idioma de la interfaz pública (ES / EN)

**Gestión de participantes**

- Lista de todos los usuarios que han enviado archivos
- Ver detalle de archivos enviados por cada persona
- Revocar acceso individual (bloquea nuevos envíos)
- Eliminar archivos de una persona
- Exportar lista de participantes (CSV)

**Historial de envíos**

- Log completo con: usuario, archivo, timestamp, tamaño, estado (éxito/error)
- Filtro por persona, fecha, tipo de archivo

---

### 4.7 Cola de Tareas Asíncrona

Las subidas a Google Drive se realizan en segundo plano para evitar timeouts en archivos grandes.

#### Configuración de Celery

```python
# celery_app.py
from celery import Celery

def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config["CELERY_RESULT_BACKEND"],
        broker=app.config["CELERY_BROKER_URL"],
    )
    celery.conf.update(app.config)
    return celery
```

#### Tarea de subida

```python
@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def upload_to_drive(self, file_path: str, user_id: int, original_name: str):
    try:
        service = get_drive_service()
        user = User.query.get(user_id)
        folder_id = get_or_create_folder(service, user.folder_name, ROOT_FOLDER_ID)
        upload_file(service, file_path, original_name, folder_id)
        # Actualizar estado en SQLite
        update_file_status(file_path, "success")
    except Exception as exc:
        update_file_status(file_path, "error")
        raise self.retry(exc=exc)
    finally:
        os.remove(file_path)  # Limpiar archivo temporal
```

---

## 5. Base de Datos (SQLite)

### Esquema de tablas

```sql
-- Sesiones de QR
CREATE TABLE qr_session (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    token       TEXT UNIQUE NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at  DATETIME,
    is_active   BOOLEAN DEFAULT 1,
    event_name  TEXT
);

-- Usuarios (personas que escanean el QR)
CREATE TABLE user (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER REFERENCES qr_session(id),
    full_name    TEXT,
    email        TEXT,
    phone        TEXT,
    folder_name  TEXT NOT NULL,         -- Nombre sanitizado para Drive
    is_blocked   BOOLEAN DEFAULT 0,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, email),
    UNIQUE(session_id, phone)
);

-- Archivos enviados
CREATE TABLE uploaded_file (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER REFERENCES user(id),
    original_name TEXT NOT NULL,
    mime_type     TEXT NOT NULL,
    file_size     INTEGER NOT NULL,      -- Bytes
    sha256_hash   TEXT NOT NULL,
    drive_file_id TEXT,                  -- ID del archivo en Drive (tras subida)
    status        TEXT DEFAULT 'pending', -- pending | success | error
    error_msg     TEXT,
    uploaded_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Configuración del sistema
CREATE TABLE app_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Valores por defecto de configuración
INSERT INTO app_config VALUES
    ('max_photos_per_user', '20'),
    ('max_videos_per_user', '5'),
    ('max_photo_size_mb', '50'),
    ('max_video_size_mb', '500'),
    ('qr_expiry_hours', '24'),
    ('required_fields', 'name,email'),   -- Campos requeridos en registro
    ('drive_root_folder_id', ''),
    ('app_language', 'es');
```

---

## 6. Integración con Google Drive

### 6.1 Opción A — Service Account

Ideal para eventos donde el organizador quiere que los archivos lleguen a **una cuenta de Drive propia de la app** o a una **carpeta compartida** de Google Workspace.

#### ¿Cuándo usar esta opción?

- La app corre en un servidor sin interacción humana.
- Se usa Google Workspace (empresa/organización).
- Se quiere automatización completa sin ventanas de login.

#### Pasos de configuración

**1. Crear la Service Account en Google Cloud Console**

```
Google Cloud Console → IAM y Admin → Cuentas de servicio
→ Crear cuenta de servicio
→ Nombre: qr-drive-uploader
→ Rol: Editor (o rol personalizado con permisos de Drive)
→ Crear clave JSON → Descargar → guardar como credentials/service_account.json
```

**2. Habilitar la API de Google Drive**

```
Google Cloud Console → Biblioteca de APIs
→ Buscar "Google Drive API"
→ Habilitar
```

**3. Compartir la carpeta raíz de Drive con la Service Account**

```
En Google Drive:
→ Carpeta del evento → Compartir
→ Ingresar el email de la Service Account (ej: qr-uploader@proyecto.iam.gserviceaccount.com)
→ Rol: Editor
→ Guardar
```

**4. Código de autenticación**

```python
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive"]

def get_drive_service_account():
    credentials = service_account.Credentials.from_service_account_file(
        "credentials/service_account.json",
        scopes=SCOPES,
    )
    return build("drive", "v3", credentials=credentials)
```

**5. Variable de entorno requerida**

```env
GOOGLE_AUTH_METHOD=service_account
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/service_account.json
DRIVE_ROOT_FOLDER_ID=1aBcDeFgHiJkLmNoPqRsTuVwXyZ  # ID de la carpeta raíz en Drive
```

---

### 6.2 Opción B — OAuth2 (cuenta personal)

Ideal cuando el organizador quiere que los archivos lleguen **a su propia cuenta de Google Drive personal** (gmail.com).

#### ¿Cuándo usar esta opción?

- El organizador tiene una cuenta personal de Google (no Workspace).
- Se prefiere que los archivos lleguen directamente al Drive del organizador.
- Desarrollo/prototipado rápido.

#### Pasos de configuración

**1. Crear credenciales OAuth2 en Google Cloud Console**

```
Google Cloud Console → APIs y Servicios → Credenciales
→ Crear credenciales → ID de cliente OAuth 2.0
→ Tipo de aplicación: Aplicación web
→ Nombre: QR Drive Uploader
→ URIs de redireccionamiento autorizados:
    http://localhost:5000/oauth2callback     (desarrollo)
    https://tu-dominio.com/oauth2callback    (producción)
→ Descargar JSON → guardar como credentials/oauth2_client_secrets.json
```

**2. Pantalla de consentimiento OAuth**

```
Google Cloud Console → APIs y Servicios → Pantalla de consentimiento de OAuth
→ Tipo: Externo (o Interno si es Workspace)
→ Nombre de la app: QR Drive Uploader
→ Ámbitos: .../auth/drive (Google Drive API)
→ Usuarios de prueba: agregar el email del organizador
```

**3. Flujo de autorización (solo se realiza una vez)**

```python
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import json, os

SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN_FILE = "credentials/oauth2_token.json"

def get_oauth2_flow():
    return Flow.from_client_secrets_file(
        "credentials/oauth2_client_secrets.json",
        scopes=SCOPES,
        redirect_uri=os.getenv("OAUTH2_REDIRECT_URI"),
    )

@app.route("/admin/authorize")
def authorize():
    flow = get_oauth2_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",          # Forzar refresh_token en cada autorización
    )
    session["oauth_state"] = state
    return redirect(auth_url)

@app.route("/oauth2callback")
def oauth2callback():
    flow = get_oauth2_flow()
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    # Guardar token para uso futuro (incluye refresh_token)
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    return redirect("/admin")

def get_drive_oauth2():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        else:
            # Redirigir al admin para re-autorizar
            raise Exception("Token expirado. Reautoriza en /admin/authorize")
    return build("drive", "v3", credentials=creds)
```

**4. Variables de entorno requeridas**

```env
GOOGLE_AUTH_METHOD=oauth2
GOOGLE_OAUTH2_CLIENT_SECRETS=credentials/oauth2_client_secrets.json
GOOGLE_OAUTH2_TOKEN_FILE=credentials/oauth2_token.json
OAUTH2_REDIRECT_URI=https://tu-dominio.com/oauth2callback
DRIVE_ROOT_FOLDER_ID=1aBcDeFgHiJkLmNoPqRsTuVwXyZ
```

---

### 6.3 Comparación entre opciones

| Criterio | Service Account | OAuth2 |
|---|---|---|
| Tipo de cuenta | Google Workspace o cualquier cuenta de Cloud | Cuenta personal o Workspace |
| Archivos van a | Carpeta compartida con la SA | Drive personal del organizador |
| Requiere login manual | No (headless, automático) | Sí (una vez, desde `/admin/authorize`) |
| Ideal para | Producción, servidores, automatización | Desarrollo, uso personal |
| Refresh token | No expira | Expira si no se usa en 6 meses |
| Cuota de Drive | Carpeta compartida (cuota del dueño) | Cuota del organizador (15 GB gratis) |
| Complejidad de setup | Media | Media-Alta (pantalla de consentimiento) |

> **Recomendación:** Usar **Service Account** para producción. Usar **OAuth2** para desarrollo o cuando el organizador quiere ver los archivos en su propio Drive sin configurar una carpeta compartida.

La app detecta cuál método usar según la variable `GOOGLE_AUTH_METHOD` en `.env`.

```python
def get_drive_service():
    method = os.getenv("GOOGLE_AUTH_METHOD", "service_account")
    if method == "oauth2":
        return get_drive_oauth2()
    return get_drive_service_account()
```

---

## 7. Seguridad y Control de Acceso

### Token de sesión del QR

- UUID4 generado con `secrets.token_urlsafe(32)` (criptográficamente seguro).
- Almacenado en base de datos con fecha de expiración.
- Cada acceso valida que el token exista, esté activo y no haya expirado.

### Rate Limiting

Implementado con `Flask-Limiter` usando Redis como backend de conteo:

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    storage_uri=os.getenv("REDIS_URL"),
)

# Máximo 10 subidas por minuto por IP
@app.route("/upload/<token>", methods=["POST"])
@limiter.limit("10/minute")
def upload(token):
    ...

# Máximo 5 intentos de registro por hora por IP
@app.route("/register/<token>", methods=["POST"])
@limiter.limit("5/hour")
def register(token):
    ...
```

### Validación de archivos

```python
import magic

def validate_file(file_storage) -> tuple[bool, str]:
    # 1. Verificar tamaño
    file_storage.seek(0, 2)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_FILE_SIZE:
        return False, f"Archivo demasiado grande ({size / 1e6:.1f} MB)"

    # 2. Verificar MIME real (no confiar en extensión)
    header = file_storage.read(2048)
    file_storage.seek(0)
    mime = magic.from_buffer(header, mime=True)
    if mime not in ALLOWED_MIME_TYPES:
        return False, f"Tipo de archivo no permitido: {mime}"

    return True, "ok"
```

### Protección del panel de administración

```python
from functools import wraps
from flask import request, Response

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
```

### Credenciales de Google — nunca en código

```
✅ Correcto: credentials/ en .gitignore + variables en .env
❌ Incorrecto: hardcodear API keys, tokens o rutas de archivos en el código fuente
```

---

## 8. Experiencia de Usuario (UX/UI)

### Flujo del usuario final (celular)

```
1. Escanea QR con la cámara del celular
2. Se abre el browser con la pantalla de registro
3. Ingresa nombre / email / teléfono
4. Se muestra la pantalla de subida con:
   - Botón grande "Seleccionar fotos/videos"
   - Indicador de límite: "Has subido X de Y fotos"
   - Lista de archivos seleccionados con previsualización
5. Toca "Enviar"
6. Barra de progreso animada durante la subida
7. Pantalla de confirmación con miniaturas de los archivos enviados
8. Opción de "Agregar más" (si no alcanzó el límite)
```

### Estados de la interfaz

| Estado | Visualización |
|---|---|
| QR expirado | Pantalla de aviso con fecha de expiración |
| QR desactivado | Pantalla de "Recepción de archivos cerrada" |
| Límite alcanzado | Pantalla de "¡Gracias! Ya enviaste el máximo de archivos" |
| Usuario bloqueado | Pantalla de "Tu acceso ha sido restringido" |
| Error de subida | Toast de error con opción de reintentar |
| Éxito | Animación de confeti + mensaje de agradecimiento |

### Soporte multiidioma (i18n)

```python
# translations/es.json
{
  "register.title": "¡Comparte tus fotos!",
  "register.name": "Tu nombre",
  "upload.button": "Seleccionar archivos",
  "upload.progress": "Subiendo {n} de {total}...",
  "upload.success": "¡Archivos enviados con éxito!"
}

# translations/en.json
{
  "register.title": "Share your photos!",
  "register.name": "Your name",
  "upload.button": "Select files",
  "upload.progress": "Uploading {n} of {total}...",
  "upload.success": "Files uploaded successfully!"
}
```

---

## 9. Diseño Visual — Estilo WEB3 Responsive

### Paleta de colores (CSS Variables)

```css
:root {
  /* Fondo oscuro principal */
  --bg-primary:      #0a0a0f;
  --bg-secondary:    #12121a;
  --bg-card:         #1a1a28;

  /* Acentos neón */
  --accent-cyan:     #0ff0fc;
  --accent-purple:   #9945ff;
  --accent-green:    #14f195;

  /* Gradiente principal */
  --gradient-main: linear-gradient(135deg, #9945ff 0%, #0ff0fc 100%);

  /* Texto */
  --text-primary:    #f0f0ff;
  --text-secondary:  #8888aa;
  --text-muted:      #555577;

  /* Bordes */
  --border-glow:     rgba(15, 240, 252, 0.3);
  --border-subtle:   rgba(255, 255, 255, 0.08);
}
```

### Tipografía

```css
/* Títulos */
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Space+Mono:wght@400;700&display=swap');

h1, h2, h3    { font-family: 'Syne', sans-serif; }
body, p, input { font-family: 'Space Mono', monospace; }
```

### Componentes clave

```css
/* Tarjeta con borde de neón */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border-glow);
  border-radius: 16px;
  box-shadow: 0 0 24px rgba(15, 240, 252, 0.08),
              inset 0 0 48px rgba(153, 69, 255, 0.04);
  padding: 2rem;
}

/* Botón principal */
.btn-primary {
  background: var(--gradient-main);
  border: none;
  border-radius: 12px;
  color: #000;
  font-family: 'Syne', sans-serif;
  font-weight: 700;
  padding: 1rem 2rem;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}
.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 32px rgba(15, 240, 252, 0.35);
}

/* Barra de progreso */
.progress-bar {
  background: var(--bg-secondary);
  border-radius: 100px;
  height: 8px;
  overflow: hidden;
}
.progress-fill {
  background: var(--gradient-main);
  height: 100%;
  transition: width 0.3s ease;
}

/* Input */
.input-field {
  background: var(--bg-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  color: var(--text-primary);
  font-family: 'Space Mono', monospace;
  padding: 0.875rem 1rem;
  width: 100%;
  transition: border-color 0.2s;
}
.input-field:focus {
  border-color: var(--accent-cyan);
  outline: none;
  box-shadow: 0 0 0 3px rgba(15, 240, 252, 0.15);
}
```

### Breakpoints responsive

```css
/* Mobile first */
.container { padding: 1rem; max-width: 100%; }

@media (min-width: 640px) {
  .container { padding: 1.5rem; max-width: 600px; margin: 0 auto; }
}

@media (min-width: 1024px) {
  .container { max-width: 960px; padding: 2rem; }
  .admin-grid { display: grid; grid-template-columns: 260px 1fr; gap: 2rem; }
}
```

---

## 10. Configuración del Entorno

### Requisitos del sistema

| Componente | Versión mínima |
|---|---|
| Python | 3.11 |
| Redis | Servicio Cloud (Upstash/Redis Cloud) |
| libmagic | 5.x (sistema) |
| pip | 23.x |

### Instalación de libmagic (sistema operativo)

```bash
# Ubuntu / Debian
sudo apt-get install libmagic1

# macOS
brew install libmagic

# Windows
pip install python-magic-bin  # Incluye binarios
```

---

## 11. Estructura de Directorios del Proyecto

```
qr-drive-uploader/
│
├── app/
│   ├── __init__.py          # Factory de la app Flask
│   ├── models.py            # Modelos SQLAlchemy
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── upload.py        # Rutas públicas (QR, registro, subida)
│   │   └── admin.py         # Rutas del panel de administración
│   ├── services/
│   │   ├── drive.py         # Lógica de integración con Google Drive
│   │   ├── qr_generator.py  # Generación de códigos QR
│   │   └── file_utils.py    # Validación, hashing, limpieza
│   ├── tasks/
│   │   └── upload_task.py   # Tareas Celery
│   ├── templates/
│   │   ├── base.html
│   │   ├── register.html    # Pantalla de registro del usuario
│   │   ├── upload.html      # Pantalla de subida
│   │   ├── success.html     # Confirmación de envío
│   │   ├── expired.html     # QR expirado
│   │   └── admin/
│   │       ├── dashboard.html
│   │       ├── settings.html
│   │       ├── participants.html
│   │       └── history.html
│   └── static/
│       ├── css/
│       │   └── main.css
│       ├── js/
│       │   ├── upload.js    # Lógica de subida + progreso
│       │   └── admin.js
│       └── img/
│
├── credentials/             # ⚠️ En .gitignore
│   ├── service_account.json
│   ├── oauth2_client_secrets.json
│   └── oauth2_token.json
│
├── translations/
│   ├── es.json
│   └── en.json
│
├── migrations/              # Flask-Migrate
│
├── logs/
│   └── app.log
│
├── tests/
│   ├── test_upload.py
│   ├── test_drive.py
│   └── test_admin.py
│
├── .env                     # ⚠️ En .gitignore
├── .env.example             # Plantilla de variables de entorno
├── .gitignore
├── celery_app.py
├── config.py
├── requirements.txt
├── run.py                   # Punto de entrada del servidor Flask
└── README.md
```

---

## 12. Variables de Entorno (.env)

```env
# ─── Flask ────────────────────────────────────────────────
FLASK_ENV=production
FLASK_SECRET_KEY=cambia-esto-por-un-secreto-muy-largo-y-aleatorio
FLASK_PORT=5000
# ─── Redis / Celery (Cloud) ───────────────────────────────
# Reemplaza la URL con la proporcionada por tu proveedor (ej. Upstash)
REDIS_URL=rediss://default:tu_password_aqui@tu-endpoint-cloud.com:6379
CELERY_BROKER_URL=rediss://default:tu_password_aqui@tu-endpoint-cloud.com:6379
CELERY_RESULT_BACKEND=rediss://default:tu_password_aqui@tu-endpoint-cloud.com:6379

# ─── Base de datos ────────────────────────────────────────
DATABASE_URL=sqlite:///data/qr_uploader.db

# ─── Redis / Celery ───────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# ─── Google Drive ─────────────────────────────────────────
GOOGLE_AUTH_METHOD=service_account   # "service_account" o "oauth2"

# Service Account
GOOGLE_SERVICE_ACCOUNT_FILE=credentials/service_account.json

# OAuth2
GOOGLE_OAUTH2_CLIENT_SECRETS=credentials/oauth2_client_secrets.json
GOOGLE_OAUTH2_TOKEN_FILE=credentials/oauth2_token.json
OAUTH2_REDIRECT_URI=https://tu-dominio.com/oauth2callback

# Carpeta raíz en Drive (ID de la carpeta del evento)
DRIVE_ROOT_FOLDER_ID=1aBcDeFgHiJkLmNoPqRsTuVwXyZ

# ─── Administración ───────────────────────────────────────
ADMIN_USERNAME=admin
ADMIN_PASSWORD=cambia-esta-contraseña

# ─── URL pública de la app ────────────────────────────────
BASE_URL=https://tu-dominio.com

# ─── Límites por defecto ──────────────────────────────────
MAX_PHOTOS_PER_USER=20
MAX_VIDEOS_PER_USER=5
MAX_PHOTO_SIZE_MB=50
MAX_VIDEO_SIZE_MB=500
QR_EXPIRY_HOURS=24

# ─── Configuración regional ───────────────────────────────
APP_LANGUAGE=es        # "es" o "en"
TIMEZONE=America/Bogota
```

---

## 13. Flujo Completo de la Aplicación

```
┌─────────────────────────────────────────────────────────────┐
│  ADMIN: Configurar evento                                   │
│  1. Login en /admin                                         │
│  2. Configurar límites y campos requeridos                  │
│  3. Ingresar ID de carpeta raíz de Drive                    │
│  4. Si OAuth2: visitar /admin/authorize (una sola vez)      │
│  5. Generar QR → descargar PNG                              │
└─────────────────────────────┬───────────────────────────────┘
                              │
                     [QR proyectado en pantalla o impreso]
                              │
┌─────────────────────────────▼───────────────────────────────┐
│  USUARIO: Escanear QR                                       │
│  1. Cámara detecta URL → abre browser                       │
│  2. Flask valida: token existe, activo, no expirado         │
│  3. Muestra formulario de registro                          │
│  4. Usuario ingresa nombre / email / teléfono               │
│  5. Flask verifica: ¿ya registrado? → recupera perfil       │
│                      ¿nuevo? → crea registro en SQLite      │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│  USUARIO: Subir archivos                                    │
│  1. Selecciona fotos/videos desde galería del celular       │
│  2. JS muestra preview y verifica límites client-side       │
│  3. POST /upload/<token> con archivos                       │
│  4. Flask valida: MIME real, tamaño, límites, duplicados    │
│  5. Si válido: guarda en /tmp, encola tarea Celery          │
│  6. Respuesta inmediata: "Archivos en cola"                 │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│  CELERY WORKER: Subir a Drive                               │
│  1. Recibe tarea con path temporal y user_id                │
│  2. Obtiene servicio de Drive (SA u OAuth2)                 │
│  3. Crea/ubica carpeta del usuario en Drive                 │
│  4. Sube archivo con nombre original                        │
│  5. Actualiza SQLite: drive_file_id, status=success         │
│  6. Elimina archivo temporal                                │
│  En caso de error: reintenta hasta 3 veces, luego status=error│
└─────────────────────────────────────────────────────────────┘
```

---

## 14. Endpoints de la API Flask

### Rutas públicas

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/upload/<token>` | Valida el QR y muestra formulario de registro |
| `POST` | `/register/<token>` | Registra al usuario y redirige a subida |
| `POST` | `/upload/<token>` | Recibe los archivos y encola las tareas |
| `GET` | `/status/<task_id>` | SSE — estado de la tarea de subida |
| `GET` | `/oauth2callback` | Callback de OAuth2 (solo si se usa ese método) |

### Rutas de administración (requieren autenticación básica)

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/admin` | Dashboard con estadísticas |
| `GET` | `/admin/settings` | Formulario de configuración |
| `POST` | `/admin/settings` | Guardar configuración |
| `GET` | `/admin/qr` | Ver/generar/descargar QR |
| `POST` | `/admin/qr/generate` | Regenerar QR (invalida el anterior) |
| `GET` | `/admin/participants` | Lista de participantes |
| `POST` | `/admin/participants/<id>/block` | Bloquear acceso de un usuario |
| `GET` | `/admin/history` | Historial de subidas |
| `GET` | `/admin/export` | Exportar participantes como CSV |
| `GET` | `/admin/authorize` | Iniciar flujo OAuth2 con Google |

---

## 15. Instalación y Puesta en Marcha

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/qr-drive-uploader.git
cd qr-drive-uploader
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### `requirements.txt` completo

```
flask>=3.0
flask-sqlalchemy>=3.1
flask-migrate>=4.0
flask-limiter>=3.5
celery>=5.3
redis>=5.0
google-api-python-client>=2.100
google-auth-oauthlib>=1.1
google-auth-httplib2>=0.2
qrcode[pil]>=7.4
python-dotenv>=1.0
python-magic>=0.4.27
Pillow>=10.0
gunicorn>=21.0
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con los valores reales
```

### 4. Inicializar la base de datos

```bash
flask db init
flask db migrate -m "Esquema inicial"
flask db upgrade
```

### 5. Configurar Redis en la nube
Dado que la aplicación requiere Redis para las tareas asíncronas y el control de tráfico, utilizaremos un servicio gestionado:
Crea una cuenta gratuita en un proveedor como Upstash (recomendado) o Redis Cloud.
Crea una base de datos Redis y copia tu URL de conexión segura (suele empezar por rediss://).
Pega esta URL en tu archivo .env en las variables REDIS_URL, CELERY_BROKER_URL y CELERY_RESULT_BACKEND.

### 6. Iniciar el worker de Celery

```bash
celery -A celery_app worker --loglevel=info --concurrency=4
```

### 7. Iniciar el servidor Flask

```bash
# Desarrollo
flask run --port 5000

# Producción (con Gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

---

## 16. Logging y Monitoreo

### Configuración de logging estructurado

```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(app):
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler = RotatingFileHandler(
        "logs/app.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
    )
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
```

### Eventos que se registran en el log

| Nivel | Evento |
|---|---|
| INFO | QR generado, usuario registrado, archivo subido exitosamente |
| WARNING | Token inválido o expirado, límite alcanzado, duplicado detectado |
| ERROR | Fallo en subida a Drive, tarea Celery fallida, MIME inválido |
| CRITICAL | Error de conexión con Google Drive, Redis no disponible |

---

## 17. Consideraciones de Escalabilidad

| Escenario | Solución |
|---|---|
| Muchas subidas simultáneas | Aumentar `--concurrency` en Celery worker |
| Archivos muy grandes (>500MB) | Implementar subida en chunks con `resumable upload` de Drive API |
| Múltiples eventos simultáneos | Agregar campo `event_id` a las tablas, permitir múltiples sesiones activas |
| Alta disponibilidad | Migrar de SQLite a PostgreSQL + múltiples workers Celery |
| Monitoreo de tareas | Agregar Flower (`celery flower`) para panel visual de Celery |
| Caché de configuración | Redis para no consultar SQLite en cada request |

---

## 18. Roadmap de Mejoras Futuras

| Prioridad | Funcionalidad |
|---|---|
| 🔴 Alta | Subida en chunks para videos grandes (Drive Resumable Upload API) |
| 🔴 Alta | Notificación por email al organizador cuando se reciben archivos |
| 🟡 Media | Galería visual en el panel de admin (miniaturas de Drive) |
| 🟡 Media | QR con marca de agua / logo del evento superpuesto |
| 🟡 Media | Migración de SQLite → PostgreSQL para producción de alta carga |
| 🟡 Media | Webhook configurable para notificar a sistemas externos |
| 🟢 Baja | App móvil (PWA) para el organizador |
| 🟢 Baja | Soporte para otros proveedores de almacenamiento (Dropbox, S3) |
| 🟢 Baja | Compresión automática de imágenes antes de subir |

---

*Documento generado para el proyecto QR Drive Uploader — versión 1.0*
*Stack: Python 3.11 · Flask 3.x · SQLite · Celery · Redis · Google Drive API*
