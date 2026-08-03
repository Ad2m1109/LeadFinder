import logging
import os
import time
from typing import Dict, Any
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

# Directory to store screenshots in the backend root
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

async def analyze_website(url: str, business_name: str) -> Dict[str, Any]:
    if not url:
        return {"seo_score": 0, "screenshot": "", "seo_issues": "No website"}
        
    if not url.startswith('http'):
        url = 'https://' + url

    logger.info(f"Analyzing website and capturing screenshot for: '{url}'")
    
    seo_score = 100
    seo_issues = []
    screenshot_filename = ""
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=True
            )
            page = await context.new_page()
            
            try:
                # Go to website and wait until page is fully loaded
                await page.goto(url, timeout=20000, wait_until="load")
                await page.wait_for_timeout(2000)
                
                # Check for Cloudflare/Anti-bot challenges
                content = await page.content()
                if "Checking your browser" in content or "Just a moment" in content or "Cloudflare" in content:
                    logger.info(f"Cloudflare/Anti-bot detected on {url}. Waiting 8 seconds for challenge to pass...")
                    await page.wait_for_timeout(8000)
                
                # Wait a tiny bit extra for animations/popups
                await page.wait_for_timeout(1500)
                
                # Capture screenshot
                safe_name = "".join(c if c.isalnum() else "_" for c in business_name.lower())
                screenshot_filename = f"{safe_name}.png"
                screenshot_path = os.path.join(SCREENSHOT_DIR, screenshot_filename)
                
                await page.screenshot(path=screenshot_path, type="png")
                logger.info(f"Screenshot saved to {screenshot_filename}")
                
                # -----------------
                # SEO Audit Rules
                # -----------------
                title = await page.title()
                if not title:
                    seo_score -= 20
                    seo_issues.append("Missing Title Tag")
                elif len(title) < 10 or len(title) > 60:
                    seo_score -= 10
                    seo_issues.append("Suboptimal Title Length")
                    
                meta_description = await page.evaluate("() => { const meta = document.querySelector('meta[name=\"description\"]'); return meta ? meta.content : null; }")
                if not meta_description:
                    seo_score -= 20
                    seo_issues.append("Missing Meta Description")
                elif len(meta_description) < 50 or len(meta_description) > 160:
                    seo_score -= 10
                    seo_issues.append("Suboptimal Meta Description Length")
                    
                viewport = await page.evaluate("() => { const meta = document.querySelector('meta[name=\"viewport\"]'); return meta ? meta.content : null; }")
                if not viewport:
                    seo_score -= 20
                    seo_issues.append("Missing Mobile Viewport (Not Mobile Responsive)")
                    
                h1_count = await page.evaluate("() => document.querySelectorAll('h1').length")
                if h1_count == 0:
                    seo_score -= 15
                    seo_issues.append("Missing H1 Tag")
                elif h1_count > 1:
                    seo_score -= 5
                    seo_issues.append("Multiple H1 Tags")
                    
            except Exception as e:
                logger.error(f"Failed to load or analyze {url}: {e}")
                seo_score = 0
                seo_issues.append("Failed to load website")
            finally:
                await browser.close()
                
    except Exception as e:
        logger.warning(f"Error in website analysis for {url}: {e}")
        seo_score = 0
        seo_issues.append("Analysis crashed")
        
    return {
        "seo_score": max(0, seo_score),
        "screenshot": f"/screenshots/{screenshot_filename}" if screenshot_filename else "",
        "seo_issues": ", ".join(seo_issues) if seo_issues else "Perfect SEO Basics"
    }
