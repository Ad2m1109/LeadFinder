import os
import csv
import logging
from typing import Dict, Any, List
from app.config import Config

logger = logging.getLogger(__name__)

class SheetService:
    def __init__(self, sheet_name: str = None):
        self.sheet_name = sheet_name or Config.GOOGLE_SHEET_NAME
        self.credentials_json = Config.GOOGLE_CREDENTIALS_JSON
        self.credentials_path = Config.GOOGLE_CREDENTIALS_FILE
        self.client = None
        self.sheet = None
        self.csv_fallback = False
        
        # Save CSV in the backend directory
        self.csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "leads.csv")
        
        self._init_sheet()
        
    def _init_sheet(self):
        try:
            # Check if we have credentials JSON string or credentials file
            has_creds = bool(self.credentials_json) or (self.credentials_path and os.path.exists(self.credentials_path))
            
            if has_creds:
                import gspread
                from google.oauth2.service_account import Credentials
                
                scopes = [
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"
                ]
                
                if self.credentials_json:
                    import json
                    creds_dict = json.loads(self.credentials_json)
                    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                    logger.info("Authenticating with Google credentials JSON string")
                else:
                    creds = Credentials.from_service_account_file(self.credentials_path, scopes=scopes)
                    logger.info(f"Authenticating with Google credentials file at {self.credentials_path}")
                
                self.client = gspread.authorize(creds)
                
                # Open or create sheet
                try:
                    self.sheet = self.client.open(self.sheet_name).sheet1
                    logger.info(f"Opened existing Google Sheet: '{self.sheet_name}'")
                except gspread.exceptions.SpreadsheetNotFound:
                    logger.info(f"Creating new Google Sheet: '{self.sheet_name}'")
                    spreadsheet = self.client.create(self.sheet_name)
                    self.sheet = spreadsheet.sheet1
                    # Set up header row
                    self.sheet.append_row(["Name", "Phone", "Website", "Rating", "Reviews", "Address", "Email", "Instagram", "Facebook", "SEO Score", "Screenshot", "SEO Issues"])
            else:
                logger.warning("No Google Sheets credentials provided. Using local CSV fallback.")
                self.csv_fallback = True
                self._init_csv()
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets service: {e}. Falling back to CSV.")
            self.csv_fallback = True
            self._init_csv()

    def _init_csv(self):
        if not os.path.exists(self.csv_path):
            try:
                os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
                with open(self.csv_path, mode='w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Name", "Phone", "Website", "Rating", "Reviews", "Address", "Email", "Instagram", "Facebook", "SEO Score", "Screenshot", "SEO Issues"])
                logger.info(f"Initialized fallback CSV at: {self.csv_path}")
            except Exception as e:
                logger.error(f"Failed to initialize fallback CSV file: {e}")

    async def append_business(self, business: Dict[str, Any]):
        row = [
            business.get("name", ""),
            business.get("phone", ""),
            business.get("website", ""),
            business.get("rating", 0.0),
            business.get("reviews", 0),
            business.get("address", ""),
            business.get("email", ""),
            business.get("instagram", ""),
            business.get("facebook", ""),
            business.get("seo_score", 0),
            business.get("screenshot", ""),
            business.get("seo_issues", "")
        ]
        
        # Always write to CSV as a backup and local storage
        try:
            self._init_csv()
            with open(self.csv_path, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row)
        except Exception as e:
            logger.error(f"Failed to write to local CSV: {e}")
            
        if not self.csv_fallback and self.sheet:
            try:
                import asyncio
                # Run blocking gspread call in a thread pool
                await asyncio.to_thread(self.sheet.append_row, row)
                logger.info(f"Successfully appended lead '{business.get('name')}' to Google Sheet.")
            except Exception as e:
                logger.error(f"Failed to append to Google Sheet: {e}. Switching to CSV-only mode.")
                self.csv_fallback = True

    def get_all_leads(self) -> List[Dict[str, Any]]:
        leads = []
        if os.path.exists(self.csv_path):
            try:
                with open(self.csv_path, mode='r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        leads.append({
                            "name": row.get("Name", ""),
                            "phone": row.get("Phone", ""),
                            "website": row.get("Website", ""),
                            "rating": float(row.get("Rating", "0.0") or "0.0"),
                            "reviews": int(row.get("Reviews", "0") or "0"),
                            "address": row.get("Address", ""),
                            "email": row.get("Email", ""),
                            "instagram": row.get("Instagram", ""),
                            "facebook": row.get("Facebook", ""),
                            "seo_score": int(row.get("SEO Score", "0") or "0"),
                            "screenshot": row.get("Screenshot", ""),
                            "seo_issues": row.get("SEO Issues", "")
                        })
            except Exception as e:
                logger.error(f"Failed to read leads from CSV: {e}")
        return leads
