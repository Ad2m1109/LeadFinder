import urllib.parse
import re
import logging
from typing import Callable, Optional
from playwright.async_api import async_playwright
from app.services.sheet import SheetService
from app.services.email import find_emails_on_website
from app.services.website import analyze_website
from app.services.ai import generate_personalized_pitch
from app.config import Config

logger = logging.getLogger(__name__)

def clean_prefix(val: str) -> str:
    if not val:
        return ""
    val = val.strip()
    if ":" in val:
        parts = val.split(":")
        first_part = parts[0].lower().strip()
        if first_part not in ["http", "https", "tel", "mailto"]:
            val = ":".join(parts[1:]).strip()
    return val

async def scrape_google_maps(
    category: str,
    city: str,
    country: str,
    sheet_service: SheetService,
    max_results: int = 50,
    on_lead_scraped: Optional[Callable[[dict], None]] = None
):
    query = f"{category} in {city}, {country}"
    search_url = f"https://www.google.com/maps/search/{urllib.parse.quote_plus(query)}"
    
    logger.info(f"Starting Google Maps scraping for query: '{query}'")
    
    async with async_playwright() as p:
        # Launch browser with generic user agent and stealth properties
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        
        page = await context.new_page()
        
        try:
            await page.goto(search_url)
            await page.wait_for_timeout(3000)
            
            # Handle Cookie Consent Banner
            try:
                # Look for accept button in various common forms
                consent_selectors = [
                    'form[action*="consent.google.com"] button',
                    'button[aria-label*="Accept all" i]',
                    'button[aria-label*="Agree" i]',
                    'button:has-text("Accept all")',
                    'button:has-text("I agree")',
                    'button:has-text("Agree")',
                    'button:has-text("Accepter")'
                ]
                for selector in consent_selectors:
                    locator = page.locator(selector).first
                    if await locator.is_visible():
                        await locator.click()
                        logger.info("Accepted Google consent dialog.")
                        await page.wait_for_timeout(2000)
                        break
            except Exception as consent_err:
                logger.debug(f"No consent dialog handled: {consent_err}")

            # Check if we were redirected directly to a single business page
            # Single business pages usually don't have the feed role but have the h1 header
            feed_selector = '[role="feed"]'
            is_feed_visible = False
            
            try:
                await page.wait_for_selector(feed_selector, timeout=5000)
                is_feed_visible = True
            except Exception:
                logger.info("Feed selector [role='feed'] not found. Checking if single business details page loaded.")

            if not is_feed_visible:
                # If we are directly on a place page, extract it as a single result
                h1_locator = page.locator('h1')
                if await h1_locator.is_visible():
                    logger.info("Directly loaded single business page. Scraping single result.")
                    business = await extract_details_panel(page)
                    if business and business.get("name"):
                        
                        website_url = business.get("website", "").lower()
                        is_social = any(domain in website_url for domain in ["facebook.com", "instagram.com", "linkedin.com", "twitter.com", "linktr.ee"])
                        if is_social:
                            if "facebook.com" in website_url and not business.get("facebook"):
                                business["facebook"] = business["website"]
                            elif "instagram.com" in website_url and not business.get("instagram"):
                                business["instagram"] = business["website"]
                            business["website"] = ""
                            business["seo_score"] = 0
                            business["screenshot"] = ""
                            business["seo_issues"] = "Social Profile"
                            
                        # Phase 2: Deep Email Crawl
                        if not business.get("email") and business.get("website"):
                            found_emails = await find_emails_on_website(business.get("website"))
                            if found_emails:
                                business["email"] = found_emails[0]
                                
                        # Phase 2: Website Analysis (SEO & Screenshot)
                        if business.get("website"):
                            analysis = await analyze_website(business.get("website"), business.get("name", "lead"))
                            business["seo_score"] = analysis.get("seo_score", 0)
                            business["screenshot"] = analysis.get("screenshot", "")
                            business["seo_issues"] = analysis.get("seo_issues", "")
                                
                        await sheet_service.append_business(business)
                        if on_lead_scraped:
                            on_lead_scraped(business)
                    return

            # We have a feed of results
            feed = page.locator(feed_selector)
            
            # Scroll to load the desired number of results
            logger.info("Scrolling the feed to load search results...")
            last_count = 0
            no_change_count = 0
            
            while True:
                links = await page.locator('a[href*="/maps/place/"]').all()
                current_count = len(links)
                logger.info(f"Loaded {current_count} business links in feed...")
                
                if current_count >= max_results:
                    logger.info(f"Reached max results limit of {max_results}.")
                    break
                
                # Scroll the feed element
                await feed.evaluate("element => element.scrollBy(0, 10000)")
                await page.wait_for_timeout(2000)
                
                links = await page.locator('a[href*="/maps/place/"]').all()
                if len(links) == current_count:
                    no_change_count += 1
                    if no_change_count >= 4:  # Stop scrolling if it doesn't load more
                        logger.info("No more businesses found. Scroll ended.")
                        break
                else:
                    no_change_count = 0
                
                # Check for end of list text
                end_text = await page.locator("text=You've reached the end of the list.").is_visible()
                if end_text:
                    logger.info("Reached the end of the Google Maps results list.")
                    break

            # Re-fetch final links
            links = await page.locator('a[href*="/maps/place/"]').all()
            logger.info(f"Found {len(links)} total businesses to scrape.")
            
            processed_urls = set()
            count = 0
            
            for link in links:
                if count >= max_results:
                    break
                    
                href = await link.get_attribute("href")
                if not href or href in processed_urls:
                    continue
                processed_urls.add(href)
                
                try:
                    # Click item to open details
                    await link.click()
                    # Wait for details panel to update/load
                    await page.wait_for_timeout(1500)
                    
                    business = await extract_details_panel(page)
                    if business and business.get("name"):
                        count += 1
                        
                        website_url = business.get("website", "").lower()
                        is_social = any(domain in website_url for domain in ["facebook.com", "instagram.com", "linkedin.com", "twitter.com", "linktr.ee"])
                        if is_social:
                            if "facebook.com" in website_url and not business.get("facebook"):
                                business["facebook"] = business["website"]
                            elif "instagram.com" in website_url and not business.get("instagram"):
                                business["instagram"] = business["website"]
                            business["website"] = ""
                            business["seo_score"] = 0
                            business["screenshot"] = ""
                            business["seo_issues"] = "Social Profile"
                        
                        # Phase 2: Deep Email Crawl
                        if not business.get("email") and business.get("website"):
                            found_emails = await find_emails_on_website(business.get("website"))
                            if found_emails:
                                business["email"] = found_emails[0]
                                
                        # Phase 2: Website Analysis (SEO & Screenshot)
                        if business.get("website"):
                            analysis = await analyze_website(business.get("website"), business.get("name", "lead"))
                            business["seo_score"] = analysis.get("seo_score", 0)
                            business["screenshot"] = analysis.get("screenshot", "")
                            business["seo_issues"] = analysis.get("seo_issues", "")
                                
                        await sheet_service.append_business(business)
                        if on_lead_scraped:
                            on_lead_scraped(business)
                            
                except Exception as e:
                    logger.error(f"Error scraping individual business details: {e}")
                    
        except Exception as e:
            logger.error(f"Scraper encountered a critical error: {e}")
        finally:
            await browser.close()
            logger.info("Playwright browser closed.")

async def extract_details_panel(page) -> Optional[dict]:
    try:
        name = ""
        rating = 0.0
        reviews = 0
        phone = ""
        website = ""
        address = ""
        
        # 1. Name: locate h1
        name_selectors = ['h1.DUwDvf', 'h1']
        for sel in name_selectors:
            locator = page.locator(sel).first
            if await locator.is_visible():
                name = await locator.inner_text()
                break
                
        if not name:
            return None
            
        # 2. Rating & Reviews
        rating_locator = page.locator('.F7nice').first
        if await rating_locator.is_visible():
            text = await rating_locator.inner_text()
            # Often "4.7(123)" or "4.7\n(123)"
            match = re.search(r'([0-9.]+)\s*\(([0-9,]+)\)', text.replace('\n', ''))
            if match:
                rating = float(match.group(1))
                reviews = int(match.group(2).replace(',', ''))
            else:
                # Fallback to separate spans
                stars_span = rating_locator.locator('span[aria-hidden="true"]').first
                if await stars_span.is_visible():
                    try:
                        rating = float(await stars_span.inner_text())
                    except ValueError:
                        pass

        # 3. Address
        address_locator = page.locator('[data-item-id="address"]').first
        if await address_locator.is_visible():
            address = await address_locator.get_attribute("aria-label")
            if not address:
                address = await address_locator.inner_text()
                
        # 4. Phone
        phone_locator = page.locator('[data-item-id^="phone:tel:"]').first
        if await phone_locator.is_visible():
            phone_attr = await phone_locator.get_attribute("data-item-id")
            if phone_attr:
                phone = phone_attr.replace("phone:tel:", "").strip()
        
        # Phone Fallback
        if not phone:
            phone_btn_selectors = [
                'button[data-tooltip*="phone" i]',
                'button[data-tooltip*="Phone" i]',
                'button[aria-label*="Phone:" i]',
                'button[aria-label*="phone" i]'
            ]
            for sel in phone_btn_selectors:
                locator = page.locator(sel).first
                if await locator.is_visible():
                    lbl = await locator.get_attribute("aria-label")
                    if lbl:
                        phone = lbl.replace("Phone: ", "").strip()
                        break
                    else:
                        phone = await locator.inner_text()
                        break

        # 5. Website
        website_locator = page.locator('[data-item-id="authority"]').first
        if await website_locator.is_visible():
            website = await website_locator.get_attribute("aria-label")
            if not website:
                website = await website_locator.inner_text()
                
        # Website Fallback
        if not website:
            web_selectors = [
                'a[data-tooltip*="website" i]',
                'a[data-tooltip*="Website" i]',
                'a[aria-label*="Website" i]',
                'a[aria-label*="website" i]'
            ]
            for sel in web_selectors:
                locator = page.locator(sel).first
                if await locator.is_visible():
                    website = await locator.get_attribute("href")
                    break

        # 6. Social Media & Email Links
        email = ""
        instagram = ""
        facebook = ""
        try:
            # Look at all anchor tags with href inside the details panel
            anchors = await page.locator('a[href]').all()
            for anchor in anchors:
                href = await anchor.get_attribute("href")
                if not href:
                    continue
                href_lower = href.lower()
                if "facebook.com" in href_lower:
                    facebook = href
                elif "instagram.com" in href_lower:
                    instagram = href
                elif href_lower.startswith("mailto:"):
                    email = href.replace("mailto:", "").split("?")[0].strip()
        except Exception as e:
            logger.debug(f"Error extracting social/email links: {e}")

        # Clean all prefixes
        name = clean_prefix(name)
        phone = clean_prefix(phone)
        website = clean_prefix(website)
        address = clean_prefix(address)

        return {
            "name": name,
            "phone": phone,
            "website": website,
            "rating": rating,
            "reviews": reviews,
            "address": address,
            "email": email,
            "instagram": instagram,
            "facebook": facebook
        }
    except Exception as e:
        logger.error(f"Error extracting details panel: {e}")
        return None
