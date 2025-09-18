import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Optional, Tuple
import os
from datetime import datetime
import logging
import re
import base64
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GoogleSheetsHelper:
    def __init__(self):
        """Initialize Google Sheets connection using service account credentials from Base64 environment variable."""
        try:
            # Define the scope
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets"
            ]
            
            # Get and decode Base64 credentials
            credentials_base64 = os.environ.get("CREDENTIALS_BASE64")
            if not credentials_base64:
                raise ValueError("CREDENTIALS_BASE64 environment variable not set")
            
            credentials_json = base64.b64decode(credentials_base64).decode('utf-8')
            creds_dict = json.loads(credentials_json)
            
            # Create credentials from the decoded dictionary
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            logger.info("Using credentials from Base64 environment variable")
            
            # Authorize and open client
            self.client = gspread.authorize(creds)
            
            # Get both Sheet IDs from environment variables
            sheet1_id = os.getenv("SHEET1_ID")
            sheet2_id = os.getenv("SHEET2_ID")
            
            if not sheet1_id or not sheet2_id:
                raise ValueError("Sheet IDs not found in environment variables")
            
            # Extract just the ID part from URLs if full URLs are provided
            self.sheet1_id = self.extract_sheet_id(sheet1_id)
            self.sheet2_id = self.extract_sheet_id(sheet2_id)
                
            # Open both spreadsheets
            self.sheet1 = self.client.open_by_key(self.sheet1_id)
            self.sheet2 = self.client.open_by_key(self.sheet2_id)
            
            logger.info("Successfully connected to both Google Sheets")
            
        except Exception as e:
            logger.error(f"Error initializing Google Sheets: {e}")
            raise

    def extract_sheet_id(self, sheet_input: str) -> str:
        """Extract just the sheet ID from a full URL or use as-is if already an ID."""
        # Pattern to match Google Sheets URL and extract ID
        url_pattern = r'https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)'
        match = re.match(url_pattern, sheet_input)
        
        if match:
            return match.group(1)
        return sheet_input
        
    def convert_date_format(self, date_str):
        """Convert date from YYYY-MM-DD to DD.MM.YYYY format for Sheet 2 worksheet names."""
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            return date_obj.strftime("%d.%m.%Y")
        except ValueError:
            return date_str  # Return original if format is already correct

    def get_uzbek_month_worksheet(self, date_str):
        """Get the correct monthly worksheet name for Sheet1 based on date."""
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        month_number = date_obj.month
        year = date_obj.year
        
        # Map month numbers to Uzbek month names
        uzbek_months = {
            1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
            5: "May", 6: "Iyun", 7: "Iyul", 8: "Avgust",
            9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr"
        }
        
        return f"{uzbek_months.get(month_number, 'Unknown')} {year}"

    def get_available_kods(self, date_str: str = None, only_empty: bool = True) -> List[str]:
        """
        Get KOD values from Sheet2 for a specific date.
        
        Args:
            date_str: Date string in format "YYYY-MM-DD". If None, uses today's date.
            only_empty: If True, returns only KODs without transport and phone info.
                       If False, returns only KODs with transport and phone info.
                       
        Returns:
            List of KOD values based on the only_empty parameter.
        """
        try:
            if date_str is None:
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            # Convert date format for Sheet 2 worksheet name (DD.MM.YYYY)
            sheet2_date = self.convert_date_format(date_str)
            
            # Try to open the worksheet for the given date
            try:
                worksheet = self.sheet2.worksheet(sheet2_date)
            except gspread.exceptions.WorksheetNotFound:
                logger.warning(f"No worksheet found for date: {sheet2_date}")
                return []
            
            # Get all values from the worksheet
            data = worksheet.get_all_values()
            
            # Extract KOD values from column D (4th column, index 3)
            kods = []
            for row in data[1:]:  # Skip header row (assuming row 1 is header)
                if len(row) > 14:  # Check if row has at least 15 columns
                    kod = row[3] if len(row) > 3 else ""  # KOD column
                    transport = row[13] if len(row) > 13 else ""  # Transport column
                    phone = row[14] if len(row) > 14 else ""  # Phone column
                    
                    # Skip empty KODs
                    if not kod.strip():
                        continue
                        
                    # Filter based on only_empty parameter
                    if only_empty:
                        # Only include if both transport and phone are empty
                        if not transport.strip() and not phone.strip():
                            kods.append(kod)
                    else:
                        # Only include if both transport and phone are filled
                        if transport.strip() and phone.strip():
                            kods.append(kod)
            
            logger.info(f"Found {len(kods)} KODs for date {sheet2_date} (only_empty={only_empty}): {kods}")
            return kods
            
        except Exception as e:
            logger.error(f"Error getting KODs from Sheet2: {e}")
            return []

    def get_sheet2_manzil(self, kod: str, date_str: str = None) -> Optional[str]:
        """
        Get MANZIL address from Sheet2 for a specific KOD and date.
        
        Args:
            kod: The KOD value to search for
            date_str: Date string in format "YYYY-MM-DD". If None, uses today's date.
            
        Returns:
            MANZIL address string or None if not found.
        """
        try:
            if date_str is None:
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            sheet2_date = self.convert_date_format(date_str)
            logger.info(f"Looking for KOD '{kod}' in Sheet2 date: {sheet2_date}")
            
            try:
                worksheet = self.sheet2.worksheet(sheet2_date)
            except gspread.exceptions.WorksheetNotFound:
                logger.warning(f"No worksheet found for date: {sheet2_date}")
                return None
            
            # Find the KOD in column D
            try:
                cell = worksheet.find(kod, in_column=4)  # Column D = KOD
                row_number = cell.row
                logger.info(f"Found KOD '{kod}' at row {row_number}")
                
                # Get MANZIL from column C
                manzil = worksheet.cell(row_number, 3).value  # Column C = MANZIL
                
                if manzil and manzil.strip():
                    logger.info(f"Found MANZIL: {manzil.strip()}")
                    return manzil.strip()
                else:
                    logger.warning(f"MANZIL is empty for KOD '{kod}'")
                    return None
                    
            except gspread.exceptions.CellNotFound:
                logger.warning(f"KOD '{kod}' not found in Sheet2 worksheet '{sheet2_date}'")
                return None
                
        except Exception as e:
            logger.error(f"Error getting MANZIL from Sheet2 for KOD '{kod}': {str(e)}")
            return None

    def get_sheet2_order_info(self, kod: str, date_str: str = None) -> Optional[Dict]:
        """Get transport and phone info from Sheet2 for a specific KOD and date."""
        try:
            if date_str is None:
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            sheet2_date = self.convert_date_format(date_str)
            
            try:
                worksheet = self.sheet2.worksheet(sheet2_date)
            except gspread.exceptions.WorksheetNotFound:
                logger.warning(f"No worksheet found for date: {sheet2_date}")
                return None
            
            data = worksheet.get_all_values()
            
            for row in data:
                if len(row) > 3 and row[3] == kod:  # KOD in column D
                    transport = row[13] if len(row) > 13 else ""  # Column N
                    phone = row[14] if len(row) > 14 else ""     # Column O
                    
                    return {
                        "Transport_raqami": transport.strip(),
                        "Haydovchi_telefon": phone.strip()
                    }
            
            return None
                
        except Exception as e:
            logger.error(f"Error getting Sheet2 order info: {e}")
            return None

    def get_existing_order(self, kod: str, date_str: str = None) -> Optional[Dict]:
        """
        Check if an order already exists for a given KOD in Sheet1.
        Uses raw data instead of get_all_records() to avoid duplicate header issues.
        """
        try:
            if date_str is None:
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            worksheet_name = self.get_uzbek_month_worksheet(date_str)
            
            # Try to get the worksheet
            try:
                worksheet = self.sheet1.worksheet(worksheet_name)
            except gspread.exceptions.WorksheetNotFound:
                logger.warning(f"Worksheet not found: {worksheet_name}")
                return None
            
            # Convert date format for Sheet1 (DD.MM.YYYY)
            compare_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
            
            # Get all values as raw data (avoiding get_all_records)
            all_data = worksheet.get_all_values()
            
            if len(all_data) < 2:  # No data beyond headers
                return None
            
            # Get headers from first row
            headers = all_data[0]
            
            # Find record with matching KOD and date
            for row in all_data[1:]:  # Skip header row
                if len(row) < len(headers):
                    continue  # Skip incomplete rows
                    
                # Create a dictionary from this row
                record = {}
                for i, header in enumerate(headers):
                    if i < len(row):
                        record[header] = row[i]
                
                record_kod = record.get("KOD", "").strip()
                record_date = record.get("Sana", "")
                
                # Convert record_date to string if it's a datetime object
                if hasattr(record_date, 'strftime'):
                    record_date = record_date.strftime("%d.%m.%Y")
                elif isinstance(record_date, str):
                    record_date = record_date.strip()
                
                if (record_kod == kod and record_date == compare_date):
                    logger.info(f"Found existing order: {record}")
                    return record
            
            logger.warning(f"No order found for KOD: {kod}, Date: {compare_date}")
            return None
                
        except Exception as e:
            logger.error(f"Error checking existing order: {e}")
            return None

    def add_order_to_sheet1(self, order_data: Dict) -> bool:
        """
        Add a new order to Sheet1 using exact column letters.
        Finds the first truly empty row instead of just appending.
        """
        try:
            # Get the date and worksheet name
            date_str = order_data.get("Sana")
            worksheet_name = self.get_uzbek_month_worksheet(date_str)
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            
            # Try to get the worksheet, create if it doesn't exist
            try:
                worksheet = self.sheet1.worksheet(worksheet_name)
            except gspread.exceptions.WorksheetNotFound:
                worksheet = self.sheet1.add_worksheet(title=worksheet_name, rows=1000, cols=20)
                logger.info(f"Created new worksheet: {worksheet_name}")
                
                # Add headers
                headers = ["ID", "Sana", "Manzil", "KOD", "Viloyat", "Transport Raqami", 
                          "Haydovchi telefon raqami", "Karta raqami", "To'lov summasi",
                          "Salarka hajmi (litr da)", "To'lov holati", "To'lov qilingan vaqt", "Izoh"]
                worksheet.append_row(headers)
            
            # Convert date format
            sana_date = date_obj.strftime("%d.%m.%Y")
            
            # Find the first truly empty row (where column A is empty)
            all_data = worksheet.get_all_values()
            next_row = 2  # Start from row 2 (after headers)
            
            # Find the first empty row by checking if column A is empty
            for i, row in enumerate(all_data[1:], start=2):  # Skip header, start from row 2
                if len(row) == 0 or not row[0].strip():  # Check if first cell (ID) is empty
                    next_row = i
                    break
            else:
                # If no empty rows found, use the next row after existing data
                next_row = len(all_data) + 1
            
            # Get the next available ID by checking existing IDs in column A
            try:
                id_column = worksheet.col_values(1)  # Column A
                if len(id_column) > 1:  # Has data beyond header
                    # Get all numeric IDs and find the max
                    numeric_ids = []
                    for cell_value in id_column[1:]:  # Skip header
                        if cell_value.isdigit():
                            numeric_ids.append(int(cell_value))
                    
                    if numeric_ids:
                        next_id = max(numeric_ids) + 1
                    else:
                        next_id = 1
                else:
                    next_id = 1
            except:
                next_id = 1
            
            # ✅ USE COLUMN LETTERS WITH VILOYAT (Column E)
            updates = [
                {'range': f'A{next_row}', 'values': [[str(next_id)]]},           # A - ID
                {'range': f'B{next_row}', 'values': [[sana_date]]},              # B - Sana
                {'range': f'C{next_row}', 'values': [[order_data.get("Manzil", "")]]},  # C - Manzil
                {'range': f'D{next_row}', 'values': [[order_data.get("KOD", "")]]},     # D - KOD
                {'range': f'E{next_row}', 'values': [[order_data.get("Viloyat", "")]]}, # E - Viloyat (NEW)
                {'range': f'F{next_row}', 'values': [[order_data.get("Transport_raqami", "")]]},  # F - Transport
                {'range': f'G{next_row}', 'values': [[order_data.get("Haydovchi_telefon", "")]]}, # G - Telefon
                {'range': f'H{next_row}', 'values': [[order_data.get("Karta_raqami", "")]]},      # H - Karta
                {'range': f'I{next_row}', 'values': [[order_data.get("To'lov_summasi", "")]]},    # I - Summa
                # Columns J and beyond are left empty intentionally
            ]
            
            # Execute batch update
            worksheet.batch_update(updates)
            
            logger.info(f"✅ Successfully added order to {worksheet_name} at row {next_row}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding order to Sheet1: {str(e)}")
            return False

    def update_order_in_sheet1(self, kod: str, order_data: Dict) -> bool:
        """
        Update an existing order in Sheet1 using column letters.
        """
        try:
            date_str = order_data.get("Sana", datetime.now().strftime("%Y-%m-%d"))
            worksheet_name = self.get_uzbek_month_worksheet(date_str)
            
            try:
                worksheet = self.sheet1.worksheet(worksheet_name)
            except gspread.exceptions.WorksheetNotFound:
                logger.warning(f"Worksheet not found: {worksheet_name}")
                return False
            
            # Convert date format for comparison
            compare_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
            
            # Find the row with matching KOD and date
            try:
                # Find KOD in column D
                kod_cells = worksheet.findall(kod, in_column=4)  # Column D = KOD
                
                for cell in kod_cells:
                    row_number = cell.row
                    # Check if date in column B matches
                    row_date = worksheet.cell(row_number, 2).value  # Column B = Sana
                    if row_date == compare_date:
                        # ✅ UPDATE USING COLUMN LETTERS
                        updates = [
                            {'range': f'C{row_number}', 'values': [[order_data.get("Manzil", "")]]},  # Manzil
                            {'range': f'E{row_number}', 'values': [[order_data.get("Transport_raqami", "")]]},  # Transport
                            {'range': f'F{row_number}', 'values': [[order_data.get("Haydovchi_telefon", "")]]}, # Telefon
                            {'range': f'G{row_number}', 'values': [[order_data.get("Karta_raqami", "")]]},      # Karta
                            {'range': f'H{row_number}', 'values': [[order_data.get("To'lov_summasi", "")]]},    # Summa
                        ]
                        
                        worksheet.batch_update(updates)
                        logger.info(f"✅ Successfully updated order in row {row_number}")
                        return True
                
                logger.warning(f"Order not found for update: {kod} in {worksheet_name}")
                return False
                
            except gspread.exceptions.CellNotFound:
                logger.warning(f"KOD not found: {kod} in {worksheet_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating order in Sheet1: {e}")
            return False

    def update_sheet2_transport_info(self, kod: str, transport: str, phone: str, date_str: str = None) -> Tuple[bool, str]:
        """
        Update transport information in Sheet2 for a specific KOD.
        Returns (success, message) tuple.
        """
        try:
            if date_str is None:
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            sheet2_date = self.convert_date_format(date_str)
            
            try:
                worksheet = self.sheet2.worksheet(sheet2_date)
            except gspread.exceptions.WorksheetNotFound:
                return False, f"❌ {sheet2_date} sanasi uchun worksheet topilmadi"
            
            data = worksheet.get_all_values()
            
            for i, row in enumerate(data):
                if len(row) > 3 and row[3] == kod:
                    # Check for date mismatch
                    if len(row) > 1 and row[1] != sheet2_date:
                        return False, f"⚠️ KOD {kod} {row[1]} sanasida joylashtirilgan, {sheet2_date} emas"
                    
                    # Update the cells
                    worksheet.update_cell(i+1, 14, transport)
                    worksheet.update_cell(i+1, 15, phone)
                    worksheet.update_cell(i+1, 8, "MBK")
                    
                    return True, f"✅ {kod} uchun transport ma'lumotlari yangilandi"
            
            return False, f"❌ {kod} topilmadi {sheet2_date} worksheetida"
            
        except Exception as e:
            return False, f"❌ Xatolik: {str(e)}"
        
        # EXTRA SAFETY FUNCTION: Get worksheet safely
    def get_worksheet_safely(self, spreadsheet, worksheet_name):
        """Safely get a worksheet without affecting others."""
        try:
            # Get fresh worksheet reference each time
            worksheet = spreadsheet.worksheet(worksheet_name)
            
            # Verify it's the correct worksheet
            if worksheet.title != worksheet_name:
                raise ValueError(f"Worksheet name mismatch: expected {worksheet_name}, got {worksheet.title}")
                
            return worksheet
        except Exception as e:
            logger.error(f"Error getting worksheet {worksheet_name}: {e}")
            return None
        
    # Instead of update_cell, use batch updates for safety
    def safe_batch_update(self, worksheet, updates):
        """Perform safe batch updates to minimize API calls and errors."""
        try:
            worksheet.batch_update(updates)
            return True
        except Exception as e:
            logger.error(f"Batch update failed: {e}")
            return False
