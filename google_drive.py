from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

class DriveHelper:
    def __init__(self, credentials, folder_id=None):
        self.service = build("drive", "v3", credentials=credentials)
        self.folder_id = folder_id

    def upload_file(self, file_path, filename):
        file_metadata = {"name": filename}
        if self.folder_id:
            file_metadata["parents"] = [self.folder_id]
        media = MediaFileUpload(file_path, resumable=True)
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink, webContentLink"
        ).execute()
        return file

    def make_file_public(self, file_id):
        self.service.permissions().create(
            fileId=file_id,
            body={"role": "reader", "type": "anyone"}
        ).execute()
