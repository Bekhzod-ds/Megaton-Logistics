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

    def get_existing_order(self, kod: str, date_str: str = None) -> Optional[Dict]:
        """
        Check if an order already exists for a given KOD in Sheet1.
        Searches in the correct monthly worksheet.
        
        Args:
            kod: The KOD value to search for.
            date_str: Date string in format "YYYY-MM-DD". If None, uses today's date.
            
        Returns:
            Dictionary with existing order data or None if not found.
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
            
            # Convert date format for comparison (Sheet1 uses DD.MM.YYYY)
            compare_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
            
            # Get all records
            records = worksheet.get_all_records()
            
            # Find record with matching KOD and date
            for record in records:
                if (record.get("KOD") == kod and 
                    record.get("Sana") == compare_date):
                    return record
                    
            return None
            
        except Exception as e:
            logger.error(f"Error checking existing order: {e}")
            return None

    def add_order_to_sheet1(self, order_data: Dict) -> bool:
        """
        Add a new order to Sheet1. Automatically detects month and writes to correct monthly worksheet.
        
        Args:
            order_data: Dictionary containing order information.
            
        Returns:
            True if successful, False otherwise.
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
                # Create new worksheet if it doesn't exist
                worksheet = self.sheet1.add_worksheet(title=worksheet_name, rows=1000, cols=20)
                logger.info(f"Created new worksheet: {worksheet_name}")
                
                # Add headers if it's a new worksheet
                headers = ["ID", "Sana", "Manzil", "KOD", "Transport Raqami", 
                          "Haydovchi telefon raqami", "Karta raqami", 
                          "To'lov summasi", "To'lov holati"]
                worksheet.append_row(headers)
            
            # Convert date format for Sheet1 (DD.MM.YYYY)
            sana_date = date_obj.strftime("%d.%m.%Y")
            
            # Get the next available ID
            try:
                existing_data = worksheet.get_all_values()
                if len(existing_data) > 1:  # Has data beyond header
                    last_id = int(existing_data[-1][0]) if existing_data[-1][0].isdigit() else 0
                    next_id = last_id + 1
                else:
                    next_id = 1
            except:
                next_id = 1
            
            # Prepare data row
            row_data = [
                str(next_id),  # ID
                sana_date,  # Sana (in DD.MM.YYYY format)
                order_data.get("Manzil", ""),
                order_data.get("KOD", ""),
                order_data.get("Transport_raqami", ""),
                order_data.get("Haydovchi_telefon", ""),
                order_data.get("Karta_raqami", ""),
                order_data.get("To'lov_summasi", ""),
                order_data.get("To'lov_holati", "")
            ]
            
            # Append the new row
            worksheet.append_row(row_data)
            
            logger.info(f"Successfully added order to Sheet1 ({worksheet_name}): {order_data.get('KOD')}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding order to Sheet1: {e}")
            return False

    def update_order_in_sheet1(self, kod: str, order_data: Dict) -> bool:
        """
        Update an existing order in Sheet1. Finds the correct worksheet based on date.
        
        Args:
            kod: The KOD value to update.
            order_data: Dictionary containing updated order information.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            date_str = order_data.get("Sana", datetime.now().strftime("%Y-%m-%d"))
            worksheet_name = self.get_uzbek_month_worksheet(date_str)
            
            # Try to get the worksheet
            try:
                worksheet = self.sheet1.worksheet(worksheet_name)
            except gspread.exceptions.WorksheetNotFound:
                logger.warning(f"Worksheet not found: {worksheet_name}")
                return False
            
            # Convert date format for comparison (Sheet1 uses DD.MM.YYYY)
            compare_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
            
            # Get all records
            records = worksheet.get_all_records()
            
            # Find the row index of the record to update
            for i, record in enumerate(records, start=2):  # Start from row 2 (skip header)
                if (record.get("KOD") == kod and 
                    record.get("Sana") == compare_date):
                    
                    # Update the row (columns C through I)
                    worksheet.update(f"C{i}", order_data.get("Manzil", ""))  # Manzil
                    worksheet.update(f"D{i}", order_data.get("KOD", ""))  # KOD
                    worksheet.update(f"E{i}", order_data.get("Transport_raqami", ""))  # Transport raqami
                    worksheet.update(f"F{i}", order_data.get("Haydovchi_telefon", ""))  # Haydovchi telefon
                    worksheet.update(f"G{i}", order_data.get("Karta_raqami", ""))  # Karta raqami
                    worksheet.update(f"H{i}", order_data.get("To'lov_summasi", ""))  # To'lov summasi
                    worksheet.update(f"I{i}", order_data.get("To'lov_holati", ""))  # To'lov holati
                    
                    logger.info(f"Successfully updated order in Sheet1 ({worksheet_name}): {kod}")
                    return True
            
            logger.warning(f"Order not found for update: {kod} in {worksheet_name}")
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
