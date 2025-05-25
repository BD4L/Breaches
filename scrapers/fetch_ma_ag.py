import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
from dateutil import parser as dateutil_parser
import re

# Assuming SupabaseClient is in utils.supabase_client
try:
    from utils.supabase_client import SupabaseClient
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from utils.supabase_client import SupabaseClient

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
MASSACHUSETTS_AG_BREACH_URL = "https://www.mass.gov/lists/data-breach-notification-reports"
SOURCE_ID_MASSACHUSETTS_AG = 11

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_flexible_ma(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', 'ongoing', 'see letter', '']:
        return None
    try:
        # mass.gov uses "Month Day, Year" e.g. "January 1, 2023"
        dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def process_massachusetts_ag_breaches():
    """
    Fetches Massachusetts AG security breach notifications, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting Massachusetts AG Security Breach Notification processing...")

    try:
        response = requests.get(MASSACHUSETTS_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Massachusetts AG breach data page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Massachusetts AG site structure (mass.gov):
    # Data is typically within a list or series of articles.
    # The main page lists links to yearly reports or directly lists breaches.
    # As of early 2024, the page "Data breach notification reports" has links to yearly pages.
    # e.g., "Data breach notifications reported in 2023"
    # Each yearly page then lists breaches, often as <li> items in a <ul> or <ol>
    # or as rows in a <table> if the structure changed.
    # Let's find links to these yearly pages first.

    yearly_page_links = []
    # Look for links containing "Data breach notifications reported in"
    # Common container classes: 'ma__document-link-list', 'ma__link-list-with-icon', or main content area.
    # Try a general approach first.
    main_content_area = soup.find('main', id='main-content') or soup # Fallback to whole soup
    
    # Pattern for yearly report links: "Data breach notifications reported in YYYY"
    # Or "Data breaches reported in YYYY"
    link_pattern = re.compile(r'data\s+breach(?:es)?\s+(?:notification(?:s)?)?\s*reported\s+in\s+(\d{4})', re.IGNORECASE)
    
    for link_tag in main_content_area.find_all('a', href=True):
        if link_pattern.search(link_tag.get_text(strip=True)):
            full_url = urljoin(MASSACHUSETTS_AG_BREACH_URL, link_tag['href'])
            if full_url not in yearly_page_links:
                yearly_page_links.append(full_url)
    
    if not yearly_page_links:
        logger.warning(f"No links to yearly breach notification pages found on {MASSACHUSETTS_AG_BREACH_URL}. Attempting to process main page directly if it contains breach list items.")
        # If no yearly links, perhaps the main page itself has the data.
        # Check for list items that look like breach notifications on the current page.
        # For now, this scraper will assume yearly pages are the primary source.
        # If this needs to change, the logic to process items directly on `soup` would go here.
        # For simplicity, if no yearly links, we stop. This can be expanded if needed.
        # A quick check: if the main page itself has list items that look like breaches.
        # e.g., if soup.select("ul.ma__executive-summary-links li") exists and items look like breaches.
        # For now, we require yearly pages as the structure seems to follow this.
        # If the main page itself has the structure of a yearly page, it should be added.
        # This check is implicitly handled if the main page's title matches the pattern and it has links
        # or if we add logic to process the main page if it contains breach items directly.
        # For now, let's assume the yearly links are the way.
        # If the main page itself is a list (e.g. only one year shown directly), this needs adjustment.
        # One way: if no yearly_page_links, and main page has <ul class="ma__executive-summary-links">
        # then add MASSACHUSETTS_AG_BREACH_URL to yearly_page_links to process it.
        if soup.select_one("ul.ma__executive-summary-links"): # A common list style on mass.gov
             logger.info("Main page contains a list that might be breaches. Adding main page URL for processing.")
             yearly_page_links.append(MASSACHUSETTS_AG_BREACH_URL) # Process current page
        else:
            logger.error(f"No yearly links found and main page does not appear to be a direct list of breaches. Cannot proceed.")
            return


    logger.info(f"Found {len(yearly_page_links)} yearly page(s) to process: {yearly_page_links}")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    total_processed = 0
    total_inserted = 0
    total_skipped = 0

    for page_url in yearly_page_links:
        logger.info(f"Processing yearly page: {page_url}")
        try:
            page_response = requests.get(page_url, headers=REQUEST_HEADERS, timeout=30)
            page_response.raise_for_status()
            page_soup = BeautifulSoup(page_response.content, 'html.parser')
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching yearly page {page_url}: {e}")
            total_skipped +=1 # Count page as skipped
            continue

        # On yearly pages (e.g., "Data breach notifications reported in 2023"):
        # Breaches are often listed in <ul> with class "ma__executive-summary-links" (or similar)
        # Each <li> in this list is a breach.
        # Inside <li>:
        #   <a> tag with href to PDF notice, text is Org Name.
        #   <div class="ma__executive-summary__content"> contains "Date posted: Month Day, Year"
        
        breach_list_ul = page_soup.select_one("ul.ma__executive-summary-links") # Common pattern on mass.gov
        if not breach_list_ul:
            # Fallback: try other common list structures or article lists
            breach_list_ul = page_soup.select_one("ul.ma__link-list--related") or \
                             page_soup.select_one("div.ma__document-Results ul") # Another list style
            if not breach_list_ul:
                logger.warning(f"Could not find the main list of breaches (ul.ma__executive-summary-links or fallbacks) on {page_url}. Skipping this page.")
                total_skipped +=1 # Count page as skipped
                continue
        
        notifications = breach_list_ul.find_all('li', recursive=False) # Get direct <li> children
        if not notifications:
            # If <li> not direct children, try finding them deeper, e.g. if wrapped in other divs by mistake
            notifications = breach_list_ul.find_all('li')

        logger.info(f"Found {len(notifications)} potential breach notifications on page {page_url}.")
        
        page_processed_count = 0
        page_inserted_count = 0
        page_skipped_count = 0

        for item_idx, li_item in enumerate(notifications):
            page_processed_count += 1
            try:
                link_tag = li_item.find('a', href=True)
                content_div = li_item.find('div', class_="ma__executive-summary__content")

                if not link_tag or not content_div:
                    logger.warning(f"Skipping item #{item_idx+1} on {page_url} due to missing link tag or content div. Link: {link_tag is not None}, Content: {content_div is not None}")
                    page_skipped_count += 1
                    continue

                org_name = link_tag.get_text(strip=True)
                item_specific_url = urljoin(page_url, link_tag['href']) # Usually PDF link
                
                date_posted_str = None
                # Date is often in "Date posted: Month Day, Year" format within content_div
                date_text_element = content_div.find(string=re.compile(r'Date\s+posted:'))
                if date_text_element:
                    date_posted_str = date_text_element.replace('Date posted:', '').strip()
                else: # Try to find any date-like string in the content_div if specific pattern fails
                    possible_date_text = content_div.get_text(strip=True)
                    # A simple regex for Month Day, Year might work if "Date posted:" is missing
                    date_match = re.search(r'([A-Za-z]+\s+\d{1,2},\s+\d{4})', possible_date_text)
                    if date_match:
                        date_posted_str = date_match.group(1)
                
                if not org_name or not date_posted_str:
                    logger.warning(f"Skipping item for '{org_name}' on {page_url} due to missing Org Name or Date Posted ('{date_posted_str}').")
                    page_skipped_count += 1
                    continue

                publication_date_iso = parse_date_flexible_ma(date_posted_str)
                if not publication_date_iso:
                    logger.warning(f"Skipping '{org_name}' from {page_url} due to unparsable date posted: '{date_posted_str}'")
                    page_skipped_count +=1
                    continue
                
                # Other details like date of breach, # affected are usually in the PDF, not on list page.
                summary = f"Data breach notification for {org_name} reported to MA AG."
                # Try to get year from page title or URL for tagging
                page_title_year_match = re.search(r'(\d{4})', page_soup.title.string if page_soup.title else "")
                page_url_year_match = re.search(r'(\d{4})', page_url)
                year_for_tag = "unknown_year"
                if page_title_year_match: year_for_tag = page_title_year_match.group(1)
                elif page_url_year_match: year_for_tag = page_url_year_match.group(1)


                raw_data = {
                    "original_date_posted": date_posted_str,
                    "pdf_notice_url": item_specific_url,
                    "source_yearly_page": page_url
                }
                raw_data_json = {k: v for k, v in raw_data.items() if v is not None}

                tags = ["massachusetts_ag", "ma_ag", f"year_{year_for_tag}"]
                
                item_data = {
                    "source_id": SOURCE_ID_MASSACHUSETTS_AG,
                    "item_url": item_specific_url, # PDF is the specific item
                    "title": org_name,
                    "publication_date": publication_date_iso,
                    "summary_text": summary,
                    "raw_data_json": raw_data_json,
                    "tags_keywords": list(set(tags))
                }
                
                # TODO: Implement check for existing record (e.g., by item_url)

                insert_response = supabase_client.insert_item(**item_data)
                if insert_response:
                    logger.info(f"Successfully inserted item for '{org_name}' from {page_url}. PDF: {item_specific_url}")
                    page_inserted_count += 1
                else:
                    logger.error(f"Failed to insert item for '{org_name}' from {page_url}.")

            except Exception as e:
                logger.error(f"Error processing list item #{item_idx+1} on page {page_url}: {li_item.get_text(strip=True)[:150]}. Error: {e}", exc_info=True)
                page_skipped_count +=1
        
        total_processed += page_processed_count
        total_inserted += page_inserted_count
        total_skipped += page_skipped_count

    logger.info(f"Finished all Massachusetts AG yearly pages. Total items processed: {total_processed}. Total items inserted: {total_inserted}. Total items skipped: {total_skipped}")


if __name__ == "__main__":
    logger.info("Massachusetts AG Security Breach Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_massachusetts_ag_breaches()
        
    logger.info("Massachusetts AG Security Breach Scraper Finished")
