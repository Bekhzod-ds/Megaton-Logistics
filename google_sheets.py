from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

class SheetsHelper:
    def __init__(self, service_json, sheet_id):
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(service_json, scopes=scopes)
        self.service = build("sheets", "v4", credentials=creds)
        self.sheet_id = sheet_id

    def get_headers(self):
        """Reads the first row of the sheet as headers."""
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.sheet_id,
            range="A1:Z1"
        ).execute()
        return result.get("values", [[]])[0]

    def find_row_by_column_value(self, column_name, value):
        """Finds the first row number where column_name matches value."""
        headers = self.get_headers()
        if column_name not in headers:
            return None
        col_index = headers.index(column_name)
        range_ = "A2:Z"
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.sheet_id,
            range=range_
        ).execute()
        rows = result.get("values", [])
        for idx, row in enumerate(rows, start=2):
            if len(row) > col_index and row[col_index] == value:
                return idx
        return None

    def update_cell_by_header(self, row_number, column_name, new_value):
        """Updates a cell using its column header."""
        headers = self.get_headers()
        if column_name not in headers:
            return
        col_index = headers.index(column_name)
        col_letter = chr(ord('A') + col_index)
        cell_range = f"{col_letter}{row_number}"
        self.service.spreadsheets().values().update(
            spreadsheetId=self.sheet_id,
            range=cell_range,
            valueInputOption="RAW",
            body={"values": [[new_value]]}
        ).execute()

    def append_row(self, row_values):
        """Appends a row to the sheet."""
        self.service.spreadsheets().values().append(
            spreadsheetId=self.sheet_id,
            range="A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row_values]}
        ).execute()
