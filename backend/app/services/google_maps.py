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
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-US"
        )
        
        page = await context.new_page()
        
        try:
            logger.info(f"Navigating to: {search_url}")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000)
            
            # Log current URL and title for debugging
            logger.info(f"Page URL: {page.url}")
            logger.info(f"Page title: {await page.title()}")
            
            # Handle Cookie/Consent Banner - try multiple approaches
            try:
                consent_selectors = [
                    'form[action*="consent.google.com"] button',
                    'button[aria-label*="Accept all" i]',
                    'button[aria-label*="Agree" i]',
                    'button[aria-label*="Accepter" i]',
                    'button:has-text("Accept all")',
                    'button:has-text("I agree")',
                    'button:has-text("Agree")',
                    'button:has-text("Accepter")',
                    'button:has-text("Reject all")',
                    '#L2AGLb',  # Common Google consent button ID
                    'button[data-id="3eEeZnuVR7c"]',
                ]
                for selector in consent_selectors:
                    try:
                        locator = page.locator(selector).first
                        if await locator.is_visible(timeout=1500):
                            await locator.click()
                            logger.info(f"Clicked consent button: {selector}")
                            await page.wait_for_timeout(3000)
                            break
                    except Exception:
                        continue
            except Exception as consent_err:
                logger.debug(f"Consent handling: {consent_err}")
            
            # Check page content for debugging
            body_text = await page.evaluate("() => document.body.innerText.substring(0, 500)")
            logger.info(f"Page body preview: {body_text[:200]}")
            
            # Check if we're on a CAPTCHA page
            if "unusual traffic" in body_text.lower() or "captcha" in body_text.lower():
                logger.error("Google CAPTCHA/bot detection triggered!")
                task_status = {"status": "failed", "error": "Google detected bot traffic. Try again later."}
                return
            
            # Check for feed
            feed_selector = '[role="feed"]'
            is_feed_visible = False
            
            try:
                await page.wait_for_selector(feed_selector, timeout=8000)
                is_feed_visible = True
                logger.info("Feed found!")
            except Exception:
                logger.info("Feed selector not found. Checking for single business page.")

            if not is_feed_visible:
                h1_locator = page.locator('h1')
                if await h1_locator.is_visible():
                    logger.info("Single business page detected.")
                    business = await extract_details_panel(page)
                    if business and business.get("name"):
                        # ... (same processing as before)
                        await sheet_service.append_business(business)
                        if on_lead_scraped:
                            on_lead_scraped(business)
                    return
                else:
                    # Take screenshot for debugging
                    logger.error(f"No feed and no h1 found. Page URL: {page.url}")
                    logger.error(f"Body text: {body_text[:500]}")
                    return

            # Scroll feed and collect links
            feed = page.locator(feed_selector)
            logger.info("Scrolling feed to load results...")
            no_change_count = 0
            
            while True:
                links = await page.locator('a[href*="/maps/place/"]').all()
                current_count = len(links)
                logger.info(f"Loaded {current_count} business links...")
                
                if current_count >= max_results:
                    break
                
                await feed.evaluate("element => element.scrollBy(0, 10000)")
                await page.wait_for_timeout(2000)
                
                links = await page.locator('a[href*="/maps/place/"]').all()
                if len(links) == current_count:
                    no_change_count += 1
                    if no_change_count >= 3:
                        break
                else:
                    no_change_count = 0
                
                try:
                    end_text = await page.locator("text=You've reached the end of the list.").is_visible()
                    if end_text:
                        break
                except:
                    pass

            links = await page.locator('a[href*="/maps/place/"]').all()
            logger.info(f"Found {len(links)} total businesses.")
            
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
                    await link.click()
                    await page.wait_for_timeout(2000)
                    
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
                        
                        if not business.get("email") and business.get("website"):
                            found_emails = await find_emails_on_website(business.get("website"))
                            if found_emails:
                                business["email"] = found_emails[0]
                                
                        if business.get("website"):
                            analysis = await analyze_website(context, business.get("website"), business.get("name", "lead"))
                            business["seo_score"] = analysis.get("seo_score", 0)
                            business["screenshot"] = analysis.get("screenshot", "")
                            business["seo_issues"] = analysis.get("seo_issues", "")
                                
                        await sheet_service.append_business(business)
                        if on_lead_scraped:
                            on_lead_scraped(business)
                        logger.info(f"Scraped {count}/{max_results}: {business.get('name')}")
                            
                except Exception as e:
                    logger.error(f"Error scraping business: {e}")
                    
        except Exception as e:
            logger.error(f"Scraper error: {e}")
        finally:
            await browser.close()
            logger.info("Browser closed.")

async def extract_details_panel(page) -> Optional[dict]:
    try:
        name = ""
        rating = 0.0
        reviews = 0
        phone = ""
        website = ""
        address = ""
        
        # Wait for details panel to settle
        await page.wait_for_timeout(1500)
        
        # 1. Name: try multiple selectors (Google Maps changes class names often)
        name_selectors = [
            'h1.DUwDvf',
            'div.lMbq3e h1',
            'h1[class*="header"]',
            'h1',
        ]
        for sel in name_selectors:
            try:
                locator = page.locator(sel).first
                if await locator.is_visible(timeout=2000):
                    text = (await locator.inner_text()).strip()
                    if text and text.lower() not in ["results", "results.", "loading..."]:
                        name = text
                        break
            except Exception:
                continue
                
        if not name:
            return None
            
        # 2. Rating & Reviews
        rating_selectors = ['.F7nice', 'span[role="img"]', 'div.F7nice']
        for sel in rating_selectors:
            try:
                rating_locator = page.locator(sel).first
                if await rating_locator.is_visible(timeout=1000):
                    text = await rating_locator.inner_text()
                    match = re.search(r'([0-9.]+)\s*\(([0-9,]+)\)', text.replace('\n', ''))
                    if match:
                        rating = float(match.group(1))
                        reviews = int(match.group(2).replace(',', ''))
                    else:
                        stars_span = rating_locator.locator('span[aria-hidden="true"]').first
                        if await stars_span.is_visible():
                            try:
                                rating = float(await stars_span.inner_text())
                            except ValueError:
                                pass
                    if rating > 0:
                        break
            except Exception:
                continue

        # 3. Address
        address_selectors = [
            '[data-item-id="address"]',
            'button[data-item-id="address"]',
            'div[data-item-id="address"]',
        ]
        for sel in address_selectors:
            try:
                address_locator = page.locator(sel).first
                if await address_locator.is_visible(timeout=1000):
                    address = await address_locator.get_attribute("aria-label") or ""
                    if not address:
                        address = (await address_locator.inner_text()).strip()
                    if address:
                        break
            except Exception:
                continue
                
        # 4. Phone
        phone_selectors = [
            '[data-item-id^="phone:tel:"]',
            'button[data-item-id^="phone:tel:"]',
        ]
        for sel in phone_selectors:
            try:
                phone_locator = page.locator(sel).first
                if await phone_locator.is_visible(timeout=1000):
                    phone_attr = await phone_locator.get_attribute("data-item-id")
                    if phone_attr:
                        phone = phone_attr.replace("phone:tel:", "").strip()
                        break
            except Exception:
                continue
        
        if not phone:
            phone_btn_selectors = [
                'button[data-tooltip*="phone" i]',
                'button[aria-label*="Phone:" i]',
                'button[aria-label*="phone" i]',
            ]
            for sel in phone_btn_selectors:
                try:
                    locator = page.locator(sel).first
                    if await locator.is_visible(timeout=1000):
                        lbl = await locator.get_attribute("aria-label") or ""
                        if lbl:
                            phone = lbl.replace("Phone: ", "").strip()
                        else:
                            phone = (await locator.inner_text()).strip()
                        if phone:
                            break
                except Exception:
                    continue

        # 5. Website
        website_selectors = [
            '[data-item-id="authority"]',
            'a[data-item-id="authority"]',
        ]
        for sel in website_selectors:
            try:
                website_locator = page.locator(sel).first
                if await website_locator.is_visible(timeout=1000):
                    website = await website_locator.get_attribute("aria-label") or ""
                    if not website:
                        website = (await website_locator.inner_text()).strip()
                    if website:
                        break
            except Exception:
                continue
                
        if not website:
            web_btn_selectors = [
                'a[data-tooltip*="website" i]',
                'a[aria-label*="Website" i]',
                'a[aria-label*="website" i]',
            ]
            for sel in web_btn_selectors:
                try:
                    locator = page.locator(sel).first
                    if await locator.is_visible(timeout=1000):
                        website = await locator.get_attribute("href") or ""
                        if website:
                            break
                except Exception:
                    continue

        # 6. Social Media & Email Links
        email = ""
        instagram = ""
        facebook = ""
        try:
            anchors = await page.locator('a[href]').all()
            for anchor in anchors:
                try:
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
                except Exception:
                    continue
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
