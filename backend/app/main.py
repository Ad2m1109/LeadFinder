import logging
import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from app.services.google_maps import scrape_google_maps
from app.services.sheet import SheetService
from app.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Lead Finder API", version="1.0.0")

# Setup screenshots directory and mount it
screenshots_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "screenshots")
os.makedirs(screenshots_dir, exist_ok=True)
app.mount("/screenshots", StaticFiles(directory=screenshots_dir), name="screenshots")

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Search request model
class SearchRequest(BaseModel):
    country: str
    city: str
    category: str
    max_results: int = 50

# Track the active scraper process status
task_status = {
    "status": "idle",       # "idle", "running", "completed", "failed"
    "query": "",
    "leads_found": 0,
    "current_lead": None,
    "error": None
}

sheet_service = SheetService()

def on_lead_scraped(lead: dict):
    """Callback triggered every time a lead is successfully scraped."""
    task_status["leads_found"] += 1
    task_status["current_lead"] = lead
    logger.info(f"Progress update: {task_status['leads_found']} leads found. Latest: {lead.get('name')}")

async def run_scraping_job(country: str, city: str, category: str, max_results: int):
    """Executes the scraper in a background thread/task."""
    global task_status, sheet_service
    
    # Reload credentials and settings before scraping
    sheet_service = SheetService()
    
    try:
        await scrape_google_maps(
            category=category,
            city=city,
            country=country,
            sheet_service=sheet_service,
            max_results=max_results,
            on_lead_scraped=on_lead_scraped
        )
        task_status["status"] = "completed"
        logger.info(f"Background scrape completed successfully. Total leads: {task_status['leads_found']}")
    except Exception as e:
        logger.error(f"Error inside background scraping job: {e}")
        task_status["status"] = "failed"
        task_status["error"] = str(e)

@app.post("/api/search")
async def start_search(request: SearchRequest, background_tasks: BackgroundTasks):
    global task_status
    
    if task_status["status"] == "running":
        raise HTTPException(
            status_code=400,
            detail="A lead search is already running. Please wait for it to finish."
        )
        
    task_status["status"] = "running"
    task_status["query"] = f"{request.category} in {request.city}, {request.country}"
    task_status["leads_found"] = 0
    task_status["current_lead"] = None
    task_status["error"] = None
    
    # Add scraping task to background
    background_tasks.add_task(
        run_scraping_job,
        country=request.country,
        city=request.city,
        category=request.category,
        max_results=request.max_results
    )
    
    logger.info(f"Triggered search background task: '{task_status['query']}'")
    return {"status": "running"}

@app.get("/api/status")
async def get_status():
    return task_status

@app.get("/api/leads")
async def get_leads():
    # Returns all leads currently saved in local storage (CSV/Sheet)
    leads = sheet_service.get_all_leads()
    return {"leads": leads}

@app.post("/api/clear")
async def clear_leads():
    """Clear local CSV file to start fresh."""
    global task_status
    if task_status["status"] == "running":
        raise HTTPException(status_code=400, detail="Cannot clear leads while scraping is active.")
        
    csv_path = sheet_service.csv_path
    if os.path.exists(csv_path):
        try:
            os.remove(csv_path)
            sheet_service._init_csv()
            logger.info("Cleared leads CSV database.")
            return {"status": "success", "message": "Leads database cleared."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to clear leads: {e}")
            
    return {"status": "success", "message": "Database already clean."}
