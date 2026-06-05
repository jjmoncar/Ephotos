import os
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import Flow

SCOPES = ["https://www.googleapis.com/auth/drive"]

def get_drive_service_account():
    creds_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/service_account.json")
    if not os.path.exists(creds_file):
        raise Exception(f"Service account file not found: {creds_file}")
    
    credentials = service_account.Credentials.from_service_account_file(
        creds_file,
        scopes=SCOPES,
    )
    return build("drive", "v3", credentials=credentials)

def get_oauth2_flow():
    client_secrets = os.getenv("GOOGLE_OAUTH2_CLIENT_SECRETS", "credentials/oauth2_client_secrets.json")
    redirect_uri = os.getenv("OAUTH2_REDIRECT_URI", "http://localhost:5000/oauth2callback")
    
    if not os.path.exists(client_secrets):
        raise Exception(f"OAuth2 client secrets file not found: {client_secrets}")
        
    return Flow.from_client_secrets_file(
        client_secrets,
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )

def get_drive_oauth2():
    token_file = os.getenv("GOOGLE_OAUTH2_TOKEN_FILE", "credentials/oauth2_token.json")
    creds = None
    
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            with open(token_file, "w") as f:
                f.write(creds.to_json())
        else:
            raise Exception("Token expirado o no encontrado. Reautoriza en /admin/authorize")
            
    return build("drive", "v3", credentials=creds)

def get_drive_service():
    method = os.getenv("GOOGLE_AUTH_METHOD", "service_account")
    if method == "oauth2":
        return get_drive_oauth2()
    return get_drive_service_account()

def get_or_create_folder(service, folder_name: str, parent_id: str) -> str:
    if not parent_id:
        parent_id = "root"
        
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

def upload_file(service, file_path: str, original_name: str, folder_id: str) -> str:
    file_metadata = {
        "name": original_name,
        "parents": [folder_id]
    }
    media = MediaFileUpload(file_path, resumable=True)
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()
    return file.get("id")
