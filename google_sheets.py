from google.oauth2 import service_account
import gspread

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"]

class SheetsHelper:
    def __init__(self, service_account_info, sheet_id):
        creds = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        self.gc = gspread.authorize(creds)
        self.sheet = self.gc.open_by_key(sheet_id)
        # use the first worksheet
        self.ws = self.sheet.get_worksheet(0)

    def get_headers(self):
        return self.ws.row_values(1)

    def find_row_by_column_value(self, column_name, value):
        headers = self.get_headers()
        if column_name not in headers:
            return None
        col_idx = headers.index(column_name) + 1
        try:
            cells = self.ws.findall(value, in_column=col_idx)
            if not cells:
                return None
            return cells[0].row
        except Exception:
            return None

    def update_cell_by_header(self, row_number, header_name, value):
        headers = self.get_headers()
        if header_name not in headers:
            # append header if missing
            headers.append(header_name)
            self.ws.insert_row(headers, index=1)
        col_idx = headers.index(header_name) + 1
        self.ws.update_cell(row_number, col_idx, value)

    def append_row(self, row_values):
        self.ws.append_row(row_values, value_input_option="USER_ENTERED")

    def update_cell_by_header(self, row_number, header_name, value):
        headers = self.get_headers()
        if header_name not in headers:
            # if header missing append it to header row and extend sheet
            headers.append(header_name)
            self.ws.update('A1', [headers])  # replace header row
        col_idx = headers.index(header_name) + 1
        self.ws.update_cell(row_number, col_idx, value)
