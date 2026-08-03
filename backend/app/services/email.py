import logging
import re
import urllib.parse
import requests
import urllib3
from typing import List, Set
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# Basic regex for email extraction
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
# Exclude common image/asset extensions that might look like emails
EXCLUDE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.css', '.js', '.svg', '.webp')

def extract_emails_from_html(html: str) -> Set[str]:
    soup = BeautifulSoup(html, 'lxml')
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.extract()
    text = soup.get_text(separator=' ')
    
    emails = set()
    for match in EMAIL_REGEX.finditer(text):
        email = match.group(0).lower()
        # Avoid fake emails from file extensions or sentry noise
        if not email.endswith(EXCLUDE_EXTENSIONS) and not email.startswith('sentry'):
            emails.add(email)
            
    # Also check mailto: links natively
    for a in soup.find_all('a', href=True):
        href = a['href'].lower()
        if href.startswith('mailto:'):
            email = href.replace('mailto:', '').split('?')[0].strip()
            if email and not email.endswith(EXCLUDE_EXTENSIONS):
                emails.add(email)
                
    return emails

def get_contact_page_links(html: str, base_url: str) -> Set[str]:
    soup = BeautifulSoup(html, 'lxml')
    contact_links = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text().lower()
        if 'contact' in text or 'about' in text or 'reach' in text:
            full_url = urllib.parse.urljoin(base_url, href)
            # Ensure we stay on the same domain
            if urllib.parse.urlparse(full_url).netloc == urllib.parse.urlparse(base_url).netloc:
                contact_links.add(full_url)
    return contact_links

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
}

async def find_emails_on_website(url: str) -> List[str]:
    if not url:
        return []
        
    if not url.startswith('http'):
        url = 'https://' + url

    logger.info(f"Crawling '{url}' for emails...")
    emails = set()
    
    try:
        # 1. Fetch homepage
        response = requests.get(url, headers=HEADERS, timeout=10, verify=False)
        if response.ok:
            html = response.text
            home_emails = extract_emails_from_html(html)
            emails.update(home_emails)
            
            # 2. Find contact pages
            contact_links = get_contact_page_links(html, url)
            
            for contact_link in list(contact_links)[:2]:
                try:
                    logger.info(f"Checking contact page: {contact_link}")
                    contact_res = requests.get(contact_link, headers=HEADERS, timeout=8, verify=False)
                    if contact_res.ok:
                        contact_emails = extract_emails_from_html(contact_res.text)
                        emails.update(contact_emails)
                except Exception as e:
                    logger.debug(f"Failed to fetch contact page {contact_link}: {e}")
                    
    except Exception as e:
        logger.warning(f"Error crawling {url}: {e}")
        
    return list(emails)
