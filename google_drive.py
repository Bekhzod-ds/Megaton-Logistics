import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

SCOPES = [
    "https://www.googleapis.com/auth/drive"
]

class DriveHelper:
    def __init__(self, service_account_info, folder_id=None):
        creds = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        self.service = build("drive", "v3", credentials=creds, cache_discovery=False)
        self.folder_id = folder_id

    def upload_file(self, local_path, filename):
        file_metadata = {"name": filename}
        if self.folder_id:
            file_metadata["parents"] = [self.folder_id]
        media = MediaFileUpload(local_path, resumable=True)
        file = self.service.files().create(body=file_metadata, media_body=media, fields="id,name,webViewLink,webContentLink").execute()
        return file

    def make_file_public(self, file_id):
        try:
            permission = {"type": "anyone", "role": "reader"}
            self.service.permissions().create(fileId=file_id, body=permission).execute()
        except Exception as e:
            # if permission fails, still continue (file may be in shared drive requiring other settings)
            print("Warning: could not set public permission:", e)
