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
MARYLAND_AG_BREACH_URL = "http://www.marylandattorneygeneral.gov/Pages/IdentityTheft/breachnotices.aspx"
# This page often has links to yearly pages, e.g., breachnotices2023.aspx
SOURCE_ID_MARYLAND_AG = 10

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_flexible_md(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', 'ongoing', 'see letter']:
        return None
    try:
        # Handle dates like "1/1/2023, 1/5/2023" - take the first one
        date_str_cleaned = date_str.split(',')[0].strip()
        dt_object = dateutil_parser.parse(date_str_cleaned)
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def fetch_and_process_yearly_page(page_url: str, supabase_client: SupabaseClient, base_url: str) -> tuple[int, int, int]:
    """
    Fetches and processes a single yearly breach notification page for Maryland AG.
    Returns counts of (processed, inserted, skipped).
    """
    logger.info(f"Processing yearly page: {page_url}")
    processed_count_page = 0
    inserted_count_page = 0
    skipped_count_page = 0

    try:
        response = requests.get(page_url, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching page {page_url}: {e}")
        return processed_count_page, inserted_count_page, skipped_count_page

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Maryland AG site structure (for yearly pages like breachnotices2023.aspx):
    # Data is typically in a <table>.
    # The table might be inside a div like <div class="ms-rtestate-field"> or <div id="DeltaPlaceHolderMain">
    # Each row <tr> in <tbody> is a breach notification.
    # Columns: "Name of Business", "Date of Breach", "Date OAG Notified", "No. of MD Residents Affected", "Copy of Notice" (link)

    data_table = None
    # Try specific container first
    main_content_container = soup.find('div', id='DeltaPlaceHolderMain')
    if main_content_container:
        data_table = main_content_container.find('table')
    
    if not data_table: # Fallback to searching less specific containers or any table
        rte_field_div = soup.find('div', class_='ms-rtestate-field')
        if rte_field_div:
            data_table = rte_field_div.find('table')
        if not data_table:
            all_tables = soup.find_all('table')
            if all_tables:
                logger.info(f"Found {len(all_tables)} table(s) on {page_url}. Using the first one assuming it's the data table.")
                data_table = all_tables[0] # This can be fragile
            else:
                logger.error(f"No tables found on page {page_url}. Cannot process.")
                return processed_count_page, inserted_count_page, skipped_count_page

    tbody = data_table.find('tbody')
    if not tbody:
        # Sometimes tables don't have a tbody, rows are directly under table
        notifications = data_table.find_all('tr')
        if notifications and notifications[0].find_all(['th', 'td']): # Check if first row looks like header
             # Heuristic: if first row has <th> or many <td>s that look like headers
            is_header = all(c.name == 'th' for c in notifications[0].find_all(recursive=False)) or len(notifications[0].find_all('td')) > 3
            if is_header and len(notifications) > 1 : notifications = notifications[1:] # Skip header row
        else:
            logger.warning(f"Table found on {page_url}, but no <tbody> and first row doesn't look like a typical header. Processing all rows.")
    else:
        notifications = tbody.find_all('tr')

    if not notifications:
        logger.info(f"No breach notification rows found in the table on {page_url}.")
        return processed_count_page, inserted_count_page, skipped_count_page
        
    logger.info(f"Found {len(notifications)} potential breach notifications on page {page_url}.")

    for row_idx, row in enumerate(notifications):
        processed_count_page += 1
        cols = row.find_all('td')
        
        if len(cols) < 3: # Expecting at least Name, Date of Breach, Date OAG Notified. Link & Affected optional.
            logger.warning(f"Skipping row {row_idx+1} on {page_url} due to insufficient columns ({len(cols)}). Content: {[c.get_text(strip=True)[:30] for c in cols]}")
            skipped_count_page += 1
            continue

        try:
            org_name = cols[0].get_text(strip=True)
            date_of_breach_str = cols[1].get_text(strip=True)
            date_oag_notified_str = cols[2].get_text(strip=True)
            
            residents_affected_str = "Not specified"
            if len(cols) > 3:
                residents_affected_str = cols[3].get_text(strip=True)

            notice_link_tag = None
            if len(cols) > 4:
                 notice_link_tag = cols[4].find('a', href=True)
            
            item_specific_url = None
            if notice_link_tag:
                item_specific_url = urljoin(base_url, notice_link_tag['href']) # Use base_url from main page for resolving relative links

            if not org_name or not date_oag_notified_str: # OAG notified date is crucial for publication
                logger.warning(f"Skipping row on {page_url} due to missing Org Name ('{org_name}') or OAG Notified Date ('{date_oag_notified_str}').")
                skipped_count_page += 1
                continue

            publication_date_iso = parse_date_flexible_md(date_oag_notified_str)
            if not publication_date_iso:
                # Fallback to date of breach if OAG notified date is not parsable
                publication_date_iso = parse_date_flexible_md(date_of_breach_str.split('-')[0].strip() if date_of_breach_str else None)
                if not publication_date_iso:
                    logger.warning(f"Skipping '{org_name}' from {page_url} due to unparsable dates: OAG Notified='{date_oag_notified_str}', Breach='{date_of_breach_str}'")
                    skipped_count_page +=1
                    continue
                else:
                    logger.info(f"Used breach date as publication date for '{org_name}' from {page_url} as OAG notified date was unparsable/missing.")

            summary = f"Security breach notification for {org_name}."
            if date_of_breach_str and date_of_breach_str.lower() not in ['n/a', 'unknown', 'pending', 'see letter']:
                summary += f" Date of Breach: {date_of_breach_str}."
            if residents_affected_str and residents_affected_str.lower() not in ['n/a', 'unknown', 'pending', 'see letter', '0', '']: # '0' might mean unknown or not applicable here
                summary += f" MD Residents Affected: {residents_affected_str}."

            raw_data = {
                "original_oag_notified_date": date_oag_notified_str,
                "date_of_breach": date_of_breach_str,
                "md_residents_affected": residents_affected_str,
                "source_yearly_page": page_url,
                "original_notice_link": item_specific_url if item_specific_url else "Not provided"
            }
            raw_data_json = {k: v for k, v in raw_data.items() if v is not None and str(v).strip().lower() not in ['n/a', 'unknown', '', 'pending', 'see letter']}

            tags = ["maryland_ag", "md_breach"]
            page_year_match = re.search(r'(\d{4})', page_url)
            if page_year_match: tags.append(f"year_{page_year_match.group(1)}")
            
            # Attempt to infer type of breach if possible from name or summary (very basic)
            if "health" in org_name.lower() or "medical" in org_name.lower():
                tags.append("healthcare")

            item_data = {
                "source_id": SOURCE_ID_MARYLAND_AG,
                "item_url": item_specific_url if item_specific_url else page_url, # Use yearly page if no specific notice
                "title": org_name,
                "publication_date": publication_date_iso,
                "summary_text": summary.strip(),
                "raw_data_json": raw_data_json,
                "tags_keywords": list(set(tags))
            }
            
            # TODO: Implement check for existing record before inserting

            insert_response = supabase_client.insert_item(**item_data)
            if insert_response:
                logger.info(f"Successfully inserted item for '{org_name}' from {page_url}. URL: {item_data['item_url']}")
                inserted_count_page += 1
            else:
                logger.error(f"Failed to insert item for '{org_name}' from {page_url}.")

        except Exception as e:
            logger.error(f"Error processing row for '{org_name if 'org_name' in locals() else 'Unknown Entity'}' on page {page_url}: {row.text[:150]}. Error: {e}", exc_info=True)
            skipped_count_page +=1
            
    return processed_count_page, inserted_count_page, skipped_count_page


def process_maryland_ag_breaches():
    """
    Fetches Maryland AG security breach main page to find links to yearly notification pages,
    then processes each yearly page.
    """
    logger.info("Starting Maryland AG Security Breach Notification processing...")
    
    try:
        session = requests.Session() # Use a session for potential cookie handling or persistent connections
        response = session.get(MARYLAND_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30, allow_redirects=True)
        response.raise_for_status()
        main_page_url = response.url # URL after redirects
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Maryland AG main breach data page {MARYLAND_AG_BREACH_URL}: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find links to yearly pages. These are usually in the main content area.
    # e.g., <a href="/Pages/IdentityTheft/breachnotices2023.aspx">2023 Breach Notices</a>
    yearly_page_links = []
    # Search within common content divs first
    content_divs = soup.find_all(['div', 'ul'], class_=['rtelist', 'ms-rtestate-field', 'dfwp-list']) # Add more as needed
    if not content_divs: content_divs = [soup] # Fallback to whole soup

    for div in content_divs:
        links = div.find_all('a', href=re.compile(r'breachnotices\d{4}\.aspx$', re.IGNORECASE))
        for link in links:
            full_url = urljoin(main_page_url, link['href']) # Resolve relative links
            if full_url not in yearly_page_links:
                yearly_page_links.append(full_url)
    
    # Also add the current main page if it looks like a list itself (e.g. if it's already a yearly page)
    # This is a heuristic; if the main page itself contains a table of breaches.
    if main_page_url.endswith(".aspx") and soup.find('table'): # Basic check
        if main_page_url not in yearly_page_links:
             # Check if it's already a yearly page pattern
            if not re.search(r'breachnotices\d{4}\.aspx$', main_page_url, re.IGNORECASE):
                 logger.info(f"Main page {main_page_url} contains a table and is not a yearly page pattern, considering it for processing.")
                 # yearly_page_links.append(main_page_url) # Add if it's a distinct list not covered by yearly links
            else: # It is a yearly page, ensure it's in the list if not already found by other means
                if main_page_url not in yearly_page_links:
                    yearly_page_links.append(main_page_url)


    if not yearly_page_links:
        logger.warning(f"No links to yearly breach notification pages found on {main_page_url}. Attempting to process main page directly if it contains a table.")
        # If no yearly links, maybe the main page itself has the data (older structure or current year)
        if soup.find('table'): # Check if main page has a table
            yearly_page_links.append(main_page_url)
        else:
            logger.error(f"No yearly links and no table found on main page {main_page_url}. Cannot proceed.")
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
        processed, inserted, skipped = fetch_and_process_yearly_page(page_url, supabase_client, main_page_url)
        total_processed += processed
        total_inserted += inserted
        total_skipped += skipped
        # Small delay between fetching yearly pages if needed, but usually not for AG sites.
        # time.sleep(1) 

    logger.info(f"Finished all Maryland AG yearly pages. Total items processed: {total_processed}. Total items inserted: {total_inserted}. Total items skipped: {total_skipped}")


if __name__ == "__main__":
    logger.info("Maryland AG Security Breach Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_maryland_ag_breaches()
        
    logger.info("Maryland AG Security Breach Scraper Finished")
