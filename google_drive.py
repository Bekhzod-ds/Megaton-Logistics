from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials

class DriveHelper:
    def __init__(self, service_json, folder_id=None):
        scopes = ["https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(service_json, scopes=scopes)
        self.service = build("drive", "v3", credentials=creds)
        self.folder_id = folder_id

    def upload_file(self, file_path, filename):
        """Uploads a file to Google Drive (Shared Drive compatible)."""
        file_metadata = {
            "name": filename,
        }
        if self.folder_id:
            file_metadata["parents"] = [self.folder_id]

        media = MediaFileUpload(file_path, resumable=True)
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id,name,webViewLink,webContentLink",
            supportsAllDrives=True
        ).execute()
        return file

    def make_file_public(self, file_id):
        """Makes a file public so anyone with the link can view it."""
        self.service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            supportsAllDrives=True
        ).execute()
