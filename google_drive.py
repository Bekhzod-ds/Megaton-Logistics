from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

class DriveHelper:
    def __init__(self, service_json, folder_id=None):
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_info(
            service_json,
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        self.service = build("drive", "v3", credentials=creds)
        self.folder_id = folder_id

        # Extract Shared Drive ID if given a folder from a Shared Drive
        self.drive_id = None
        if self.folder_id:
            try:
                folder = self.service.files().get(
                    fileId=self.folder_id,
                    fields="id, driveId",
                    supportsAllDrives=True
                ).execute()
                self.drive_id = folder.get("driveId")
            except Exception as e:
                print("Warning: Could not get driveId for folder:", e)

    def upload_file(self, file_path, filename):
        file_metadata = {"name": filename}
        if self.folder_id:
            file_metadata["parents"] = [self.folder_id]
        if self.drive_id:
            file_metadata["driveId"] = self.drive_id

        media = MediaFileUpload(file_path, resumable=True)
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink, webContentLink",
            supportsAllDrives=True
        ).execute()
        return file

    def make_file_public(self, file_id):
        try:
            self.service.permissions().create(
                fileId=file_id,
                body={"role": "reader", "type": "anyone"},
                supportsAllDrives=True
            ).execute()
        except Exception as e:
            print("Warning: Could not make file public:", e)
