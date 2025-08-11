from googleapiclient.discovery import build
from google.oauth2 import service_account

class SheetsHelper:
    def __init__(self, service_json, spreadsheet_id):
        creds = service_account.Credentials.from_service_account_info(service_json)
        self.service = build("sheets", "v4", credentials=creds)
        self.spreadsheet_id = spreadsheet_id

    def find_row_by_id(self, sheet_name, search_value, id_column_name):
        """
        Finds the row index where the given ID is located.
        Returns the row number (1-based) or None if not found.
        """
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"{sheet_name}!A1:Z"
        ).execute()

        values = result.get("values", [])
        if not values:
            return None

        # Find the column index for the given header name
        header = values[0]
        try:
            col_index = header.index(id_column_name)
        except ValueError:
            raise Exception(f"Column '{id_column_name}' not found in sheet.")

        for i, row in enumerate(values[1:], start=2):  # start=2 because row 1 is headers
            if len(row) > col_index and row[col_index] == str(search_value):
                return i

        return None

    def update_cell(self, sheet_name, row, column_name, new_value):
        """
        Updates the cell in the given row and column header with the new value.
        """
        # Get headers to find column index
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"{sheet_name}!1:1"
        ).execute()

        headers = result.get("values", [[]])[0]
        try:
            col_index = headers.index(column_name)
        except ValueError:
            raise Exception(f"Column '{column_name}' not found.")

        # Convert col_index (0-based) to column letter
        col_letter = chr(ord('A') + col_index)
        cell_range = f"{sheet_name}!{col_letter}{row}"

        # Update the cell
        self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=cell_range,
            valueInputOption="RAW",
            body={"values": [[new_value]]}
        ).execute()
