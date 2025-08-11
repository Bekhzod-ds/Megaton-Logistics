from googleapiclient.discovery import build

class SheetsHelper:
    def __init__(self, credentials, sheet_id):
        self.service = build("sheets", "v4", credentials=credentials)
        self.sheet_id = sheet_id

    def update_screenshot_link(self, row_id, link):
        # Adjust range based on your sheet structure
        # Assumes first column is ID, and screenshot column is column H (8th column)
        sheet = self.service.spreadsheets().values().get(
            spreadsheetId=self.sheet_id,
            range="A:H"
        ).execute()

        values = sheet.get("values", [])
        target_row = None
        for idx, row in enumerate(values):
            if row and row[0] == row_id:
                target_row = idx + 1  # 1-based index for Sheets
                break

        if target_row:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range=f"H{target_row}",
                valueInputOption="USER_ENTERED",
                body={"values": [[link]]}
            ).execute()
