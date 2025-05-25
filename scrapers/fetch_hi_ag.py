import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
from dateutil import parser as dateutil_parser

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
HAWAII_AG_BREACH_URL = "https://cca.hawaii.gov/ocp/notices/security-breach/"
SOURCE_ID_HAWAII_AG = 6

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_flexible_hi(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO 8601 format string or None if parsing fails or input is invalid.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided']:
        return None
    try:
        dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def process_hawaii_ag_breaches():
    """
    Fetches Hawaii AG security breach notifications, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting Hawaii AG Security Breach Notification processing...")

    try:
        response = requests.get(HAWAII_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Hawaii AG breach data page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Hawaii AG site structure:
    # Data is typically within a <table>. The table might be inside a div with class 'entry-content'.
    # Each row <tr> in <tbody> is a breach notification.
    
    data_table = None
    entry_content_div = soup.find('div', class_='entry-content') # Common WordPress class
    if entry_content_div:
        data_table = entry_content_div.find('table')
    
    if not data_table:
        # Fallback: try to find any table if not in 'entry-content'
        all_tables = soup.find_all('table')
        if all_tables:
            logger.info(f"Found {len(all_tables)} table(s) outside 'entry-content'. Trying the first one.")
            data_table = all_tables[0] # This might be fragile
        else:
            logger.error("Could not find the breach data table (neither in 'entry-content' nor any other table on page). Page structure might have changed.")
            # logger.debug(f"Page content sample (first 500 chars): {response.text[:500]}")
            return
            
    tbody = data_table.find('tbody')
    if not tbody:
        logger.error("Table found, but it does not contain a <tbody> element. Cannot process rows.")
        return
        
    notifications = tbody.find_all('tr')
    logger.info(f"Found {len(notifications)} potential breach notifications in the table.")

    if not notifications:
        logger.warning("No rows found in the table body. The table might be empty or structured differently.")
        return

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    inserted_count = 0
    processed_count = 0
    skipped_count = 0

    # Column headers are usually: "Date Posted", "Organization Name", "Date of Breach", "Notice"
    # These can change, so robust parsing or clear indexing is important.
    # Assuming a fixed column order for simplicity here, but header parsing would be more robust.

    for row_idx, row in enumerate(notifications):
        processed_count += 1
        cols = row.find_all('td')
        
        if len(cols) < 3: # Expecting at least Date Posted, Org Name, Date of Breach. Notice is optional.
            logger.warning(f"Skipping row {row_idx+1} due to insufficient columns ({len(cols)}). Row content: {[c.get_text(strip=True)[:30] for c in cols]}")
            skipped_count += 1
            continue

        try:
            date_posted_str = cols[0].get_text(strip=True)
            org_name = cols[1].get_text(strip=True)
            date_of_breach_str = cols[2].get_text(strip=True)
            
            notice_link_tag = None
            if len(cols) > 3: # Notice column might not always be present or have a link
                 notice_link_tag = cols[3].find('a', href=True)
            
            item_specific_url = None
            if notice_link_tag:
                item_specific_url = urljoin(HAWAII_AG_BREACH_URL, notice_link_tag['href'])

            if not org_name or not date_posted_str:
                logger.warning(f"Skipping row {row_idx+1} due to missing Organization Name ('{org_name}') or Date Posted ('{date_posted_str}').")
                skipped_count += 1
                continue

            publication_date_iso = parse_date_flexible_hi(date_posted_str)
            if not publication_date_iso:
                # Try parsing date_of_breach_str if date_posted_str failed
                publication_date_iso = parse_date_flexible_hi(date_of_breach_str.split('-')[0].strip() if date_of_breach_str else None)
                if not publication_date_iso:
                    logger.warning(f"Skipping '{org_name}' due to unparsable primary date: Posted='{date_posted_str}', Breach='{date_of_breach_str}'")
                    skipped_count +=1
                    continue
                else:
                     logger.info(f"Used breach date as publication date for '{org_name}' as posted date was unparsable or missing.")


            raw_data = {
                "original_date_posted": date_posted_str,
                "date_of_breach": date_of_breach_str if date_of_breach_str else "Not specified",
                "original_notice_link": item_specific_url if item_specific_url else "Not provided on list page"
                # No "residents affected" or "type of breach" usually on this list page.
            }
            raw_data_json = {k: v for k, v in raw_data.items() if v is not None and v.strip().lower() not in ['n/a', 'unknown', '']}

            # Summary: since type of breach isn't listed, use a generic one or one based on org type if possible.
            summary = f"Security breach notification for {org_name}."
            if date_of_breach_str and date_of_breach_str.lower() not in ['n/a', 'unknown', 'pending']:
                summary += f" Breach occurred around: {date_of_breach_str}."

            tags = ["hawaii_ag", "hi_breach", "security_notification"]
            # If PDF content were fetched, more tags could be derived.

            item_data = {
                "source_id": SOURCE_ID_HAWAII_AG,
                "item_url": item_specific_url if item_specific_url else HAWAII_AG_BREACH_URL,
                "title": org_name,
                "publication_date": publication_date_iso,
                "summary_text": summary,
                "raw_data_json": raw_data_json,
                "tags_keywords": list(set(tags))
            }
            
            # TODO: Implement check for existing record before inserting

            insert_response = supabase_client.insert_item(**item_data)
            if insert_response:
                logger.info(f"Successfully inserted item for '{org_name}'. URL: {item_data['item_url']}")
                inserted_count += 1
            else:
                logger.error(f"Failed to insert item for '{org_name}'.")

        except Exception as e:
            logger.error(f"Error processing row for '{org_name if 'org_name' in locals() else 'Unknown Entity'}': {row.text[:150]}. Error: {e}", exc_info=True)
            skipped_count +=1

    logger.info(f"Finished processing Hawaii AG breaches. Total rows processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("Hawaii AG Security Breach Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_hawaii_ag_breaches()
        
    logger.info("Hawaii AG Security Breach Scraper Finished")
