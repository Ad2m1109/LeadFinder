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

# Enable CORS BEFORE anything else
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup screenshots directory and mount it (AFTER CORS)
screenshots_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "screenshots")
os.makedirs(screenshots_dir, exist_ok=True)
app.mount("/screenshots", StaticFiles(directory=screenshots_dir), name="screenshots")

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

@app.get("/")
async def root():
    return {"status": "ok", "service": "LeadFinder API"}

@app.get("/api/routes")
async def list_routes():
    return {"routes": [r.path for r in app.routes if hasattr(r, "path")]}

@app.get("/api/test-scrape")
async def test_scrape():
    """Test if Playwright/Chromium works on this server."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto("https://www.google.com", timeout=15000)
            title = await page.title()
            await browser.close()
            return {"status": "ok", "title": title, "message": "Playwright works!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/debug-maps")
async def debug_maps():
    """Debug Google Maps scraping to see what's happening."""
    import urllib.parse
    try:
        from playwright.async_api import async_playwright
        query = "Restaurant in Tirana, Albania"
        search_url = f"https://www.google.com/maps/search/{urllib.parse.quote_plus(query)}"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = await context.new_page()
            
            await page.goto(search_url)
            await page.wait_for_timeout(5000)
            
            # Check for consent dialog
            consent_found = False
            try:
                for selector in ['button:has-text("Accept all")', 'button:has-text("I agree")', 'button:has-text("Accepter")']:
                    loc = page.locator(selector).first
                    if await loc.is_visible(timeout=2000):
                        await loc.click()
                        consent_found = True
                        await page.wait_for_timeout(2000)
                        break
            except:
                pass
            
            # Check page content
            title = await page.title()
            url = page.url
            content_snippet = (await page.content())[:2000]
            
            # Check for feed
            feed_visible = False
            try:
                feed = page.locator('[role="feed"]')
                feed_visible = await feed.is_visible(timeout=3000)
            except:
                pass
            
            # Check for business links
            links = await page.locator('a[href*="/maps/place/"]').all()
            
            # Check for h1
            h1_text = ""
            try:
                h1 = page.locator('h1').first
                if await h1.is_visible(timeout=2000):
                    h1_text = await h1.inner_text()
            except:
                pass
            
            await browser.close()
            
            return {
                "query": query,
                "url": url,
                "title": title,
                "consent_handled": consent_found,
                "feed_visible": feed_visible,
                "business_links_count": len(links),
                "h1_text": h1_text,
                "content_snippet": content_snippet[:500]
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}

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
    """Clear local CSV file and old screenshots to start fresh."""
    global task_status
    if task_status["status"] == "running":
        raise HTTPException(status_code=400, detail="Cannot clear leads while scraping is active.")
        
    csv_path = sheet_service.csv_path
    if os.path.exists(csv_path):
        try:
            os.remove(csv_path)
            sheet_service._init_csv()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to clear leads: {e}")

    # Clear old screenshots
    screenshots_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "screenshots")
    if os.path.exists(screenshots_dir):
        for f in os.listdir(screenshots_dir):
            if f.endswith(".png"):
                try:
                    os.remove(os.path.join(screenshots_dir, f))
                except Exception:
                    pass

    logger.info("Cleared leads CSV and screenshots.")
    return {"status": "success", "message": "Leads database and screenshots cleared."}
