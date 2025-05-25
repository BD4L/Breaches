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
OKLAHOMA_CYBER_BREACH_URL = "https://cybersecurity.ok.gov/breaches"
SOURCE_ID_OKLAHOMA_CYBER = 16

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_flexible_ok(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', 'ongoing', 'see letter', '']:
        return None
    try:
        dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def process_oklahoma_cyber_breaches():
    """
    Fetches Oklahoma Cybersecurity breach notifications, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting Oklahoma Cybersecurity Breach Notification processing...")

    try:
        response = requests.get(OKLAHOMA_CYBER_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Oklahoma Cybersecurity breach data page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Oklahoma Cybersecurity site structure (cybersecurity.ok.gov/breaches):
    # Data is typically presented in a table.
    # The table is usually within a main content div.
    # Example: <div class="container"> ... <table class="table table-striped"> ... </table> ... </div>
    # Each row <tr> in <tbody> is a breach.
    
    data_table = None
    # Try to find a table with specific classes or within a known container
    # Common Drupal/Gov site pattern: table inside div.region-content or similar
    content_region = soup.find('div', id='content-area') # Specific to this site's layout
    if content_region:
        data_table = content_region.find('table', class_=re.compile(r'table')) # e.g. table-striped, table
    
    if not data_table: # Fallback to any table if specific container not found
        all_tables = soup.find_all('table', class_=re.compile(r'table'))
        if all_tables:
            logger.info(f"Found {len(all_tables)} table(s) with 'table' class. Using the first one.")
            data_table = all_tables[0]
        else:
            logger.error("Could not find a suitable data table (e.g., with class 'table' or in 'div#content-area'). Page structure might have changed.")
            # logger.debug(f"Page content sample (first 1000 chars): {response.text[:1000]}")
            return
            
    tbody = data_table.find('tbody')
    if not tbody:
        # If no tbody, check if rows are directly under table (less common for data tables but possible)
        notifications = data_table.find_all('tr')
        if notifications and notifications[0].find_all('th'): # Check if first row is header
            notifications = notifications[1:] # Skip header
        elif not notifications:
            logger.warning("Table found, but it does not contain a <tbody> or any direct <tr> data rows.")
            return
    else:
        notifications = tbody.find_all('tr')

    if not notifications:
        logger.info("No breach notification rows found in the table.")
        return
        
    logger.info(f"Found {len(notifications)} potential breach notifications in the table.")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    inserted_count = 0
    processed_count = 0
    skipped_count = 0

    # Expected column order (inspect current site to confirm):
    # 0: Entity Name
    # 1: Date of Breach
    # 2: Date Reported
    # 3: Number of Oklahoma Residents Affected (Optional)
    # 4: Type of Breach / Link to Notice (Can be mixed or one of these)

    for row_idx, row in enumerate(notifications):
        processed_count += 1
        cols = row.find_all('td')
        
        if len(cols) < 3: # Need at least Entity, Breach Date, Reported Date
            logger.warning(f"Skipping row {row_idx+1} due to insufficient columns ({len(cols)}). Content: {[c.get_text(strip=True)[:30] for c in cols]}")
            skipped_count += 1
            continue

        try:
            entity_name = cols[0].get_text(strip=True)
            date_of_breach_str = cols[1].get_text(strip=True)
            date_reported_str = cols[2].get_text(strip=True)
            
            residents_affected_str = "Not specified"
            if len(cols) > 3:
                residents_affected_str = cols[3].get_text(strip=True)

            type_of_breach = "Not specified"
            item_specific_url = None # Link to a detailed notice/PDF

            # Column 4 might be "Type of Breach" or "Link to Notice", or both.
            if len(cols) > 4:
                col4_cell = cols[4]
                link_tag = col4_cell.find('a', href=True)
                if link_tag:
                    item_specific_url = urljoin(OKLAHOMA_CYBER_BREACH_URL, link_tag['href'])
                    # If link text is not just "Notice" or "PDF", it might be type of breach
                    link_text = link_tag.get_text(strip=True)
                    if link_text.lower() not in ['notice', 'pdf', 'view', 'details', 'letter']:
                        type_of_breach = link_text
                    elif col4_cell.get_text(strip=True) != link_text : # If other text besides link in cell
                        type_of_breach = col4_cell.get_text(strip=True).replace(link_text, "").strip()

                else: # No link, text is likely type of breach
                    type_of_breach = col4_cell.get_text(strip=True)
            
            # If type_of_breach is still "Not specified" but residents_affected_str looks like text, it might be type_of_breach
            # This happens if columns shift or "residents affected" is not a number.
            if type_of_breach == "Not specified" and residents_affected_str and not residents_affected_str.isdigit():
                # Check if residents_affected_str looks like a type of breach rather than a number
                if len(residents_affected_str) > 3 and any(c.isalpha() for c in residents_affected_str): # Basic check
                    type_of_breach = residents_affected_str
                    residents_affected_str = "Not specified" # Reset since it was actually type of breach


            if not entity_name or not date_reported_str:
                logger.warning(f"Skipping row due to missing Entity Name ('{entity_name}') or Date Reported ('{date_reported_str}').")
                skipped_count += 1
                continue

            publication_date_iso = parse_date_flexible_ok(date_reported_str)
            if not publication_date_iso:
                # Fallback to date of breach if reported date is not parsable
                publication_date_iso = parse_date_flexible_ok(date_of_breach_str.split('-')[0].strip() if date_of_breach_str else None)
                if not publication_date_iso:
                    logger.warning(f"Skipping '{entity_name}' due to unparsable dates: Reported='{date_reported_str}', Breach='{date_of_breach_str}'")
                    skipped_count +=1
                    continue
                else:
                    logger.info(f"Used breach date as publication date for '{entity_name}' as reported date was unparsable/missing.")
                
                
            summary = f"Security breach at {entity_name}."
            if type_of_breach and type_of_breach.lower() != 'not specified':
                summary += f" Type: {type_of_breach}."
            if date_of_breach_str and date_of_breach_str.lower() not in ['n/a', 'unknown', 'pending']:
                summary += f" Breach Date(s): {date_of_breach_str}."
            if residents_affected_str and residents_affected_str.lower() not in ['n/a', 'unknown', 'pending', 'not specified'] and residents_affected_str.isdigit():
                summary += f" OK Residents Affected: {residents_affected_str}."

            raw_data = {
                "original_date_reported": date_reported_str,
                "date_of_breach": date_of_breach_str,
                "ok_residents_affected": residents_affected_str if residents_affected_str.isdigit() else "Not specified",
                "type_of_breach_from_table": type_of_breach,
                "original_notice_link": item_specific_url if item_specific_url else "Not provided on list page"
            }
            raw_data_json = {k: v for k, v in raw_data.items() if v is not None and str(v).strip().lower() not in ['n/a', 'unknown', '', 'pending', 'not specified']}

            tags = ["oklahoma_cyber", "ok_cyber"]
            if type_of_breach and type_of_breach.lower() != 'not specified':
                tags.append(type_of_breach.lower().replace(" ", "_").replace("/", "_"))
            
            # Basic tagging from entity name or type of breach
            combined_text_for_tags = (entity_name + " " + type_of_breach).lower()
            if "ransomware" in combined_text_for_tags : tags.append("ransomware")
            if "phishing" in combined_text_for_tags: tags.append("phishing")
            if "unauthorized access" in combined_text_for_tags: tags.append("unauthorized_access")


            item_data = {
                "source_id": SOURCE_ID_OKLAHOMA_CYBER,
                "item_url": item_specific_url if item_specific_url else OKLAHOMA_CYBER_BREACH_URL,
                "title": entity_name,
                "publication_date": publication_date_iso,
                "summary_text": summary.strip(),
                "raw_data_json": raw_data_json,
                "tags_keywords": list(set(tags))
            }
            
            # TODO: Implement check for existing record before inserting

            insert_response = supabase_client.insert_item(**item_data)
            if insert_response:
                logger.info(f"Successfully inserted item for '{entity_name}'. URL: {item_data['item_url']}")
                inserted_count += 1
            else:
                logger.error(f"Failed to insert item for '{entity_name}'.")

        except Exception as e:
            logger.error(f"Error processing row for '{entity_name if 'entity_name' in locals() else 'Unknown Entity'}': {row.text[:150]}. Error: {e}", exc_info=True)
            skipped_count +=1

    logger.info(f"Finished processing Oklahoma Cybersecurity breaches. Total items processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("Oklahoma Cybersecurity Breach Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_oklahoma_cyber_breaches()
        
    logger.info("Oklahoma Cybersecurity Breach Scraper Finished")
