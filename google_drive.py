from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

class DriveHelper:
    def __init__(self, service_json, folder_id=None):
        # Authenticate with Service Account JSON
        creds = service_account.Credentials.from_service_account_info(service_json)
        self.service = build("drive", "v3", credentials=creds)
        self.folder_id = folder_id  # folder in shared drive (optional)

    def upload_file(self, local_path, filename):
        file_metadata = {
            "name": filename,
            "parents": [self.folder_id] if self.folder_id else None
        }

        # if uploading to shared drive, must specify supportsAllDrives=True
        media = MediaFileUpload(local_path, resumable=True)
        uploaded = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink, webContentLink",
            supportsAllDrives=True
        ).execute()
        return uploaded

    def make_file_public(self, file_id):
        # allow "anyone with the link" to view
        self.service.permissions().create(
            fileId=file_id,
            body={"role": "reader", "type": "anyone"},
            supportsAllDrives=True
        ).execute()
