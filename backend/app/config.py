import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Lead Finder Results")
    GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", None)
    GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    
    # Scraper settings
    MAX_SCRAPE_RESULTS = int(os.getenv("MAX_SCRAPE_RESULTS", "50"))
    
    # Server settings
    PORT = int(os.getenv("PORT", "8000"))
    HOST = os.getenv("HOST", "0.0.0.0")
