import logging
import os
from typing import Dict, Any
from playwright.async_api import BrowserContext

logger = logging.getLogger(__name__)

SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

async def analyze_website(context: BrowserContext, url: str, business_name: str) -> Dict[str, Any]:
    if not url:
        return {"seo_score": 0, "screenshot": "", "seo_issues": "No website"}

    if not url.startswith('http'):
        url = 'https://' + url

    logger.info(f"Analyzing website: '{url}'")

    seo_score = 100
    seo_issues = []
    screenshot_filename = ""
    page = None

    try:
        page = await context.new_page()

        try:
            await page.goto(url, timeout=15000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            content = await page.content()
            if "Checking your browser" in content or "Just a moment" in content or "Cloudflare" in content:
                await page.wait_for_timeout(6000)

            # Capture screenshot
            safe_name = "".join(c if c.isalnum() else "_" for c in business_name.lower())
            screenshot_filename = f"{safe_name}.png"
            screenshot_path = os.path.join(SCREENSHOT_DIR, screenshot_filename)
            await page.screenshot(path=screenshot_path, type="png")
            logger.info(f"Screenshot saved: {screenshot_filename}")

            # SEO Audit
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
            if page:
                await page.close()

    except Exception as e:
        logger.warning(f"Error in website analysis for {url}: {e}")
        seo_score = 0
        seo_issues.append("Analysis crashed")

    return {
        "seo_score": max(0, seo_score),
        "screenshot": f"/screenshots/{screenshot_filename}" if screenshot_filename else "",
        "seo_issues": ", ".join(seo_issues) if seo_issues else "Perfect SEO Basics"
    }
