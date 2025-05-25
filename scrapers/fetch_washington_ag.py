import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
from dateutil import parser as dateutil_parser # For flexible date parsing

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
WASHINGTON_AG_BREACH_INITIAL_URL = "http://www.atg.wa.gov/data-breach-notifications"
# Placeholder for the source_id from the 'data_sources' table in Supabase
SOURCE_ID_WASHINGTON_AG = 5 

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_flexible_wa(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Handles common variations like "N/A", "Unknown".
    Returns ISO 8601 format string or None if parsing fails or input is invalid.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided']:
        return None
    try:
        # Handle cases like "Spring 2023" - dateutil might parse this to a specific date, e.g. March 1st.
        # If more specific handling for seasons or vague terms is needed, add it here.
        if "spring" in date_str.lower(): # Example: "Spring 2023" -> "03/01/2023" (approximate)
            year = date_str.lower().split("spring")[-1].strip()
            dt_object = dateutil_parser.parse(f"March 1, {year}")
        elif "summer" in date_str.lower():
            year = date_str.lower().split("summer")[-1].strip()
            dt_object = dateutil_parser.parse(f"June 1, {year}")
        elif "fall" in date_str.lower() or "autumn" in date_str.lower():
            year = date_str.lower().split("fall")[-1].strip() if "fall" in date_str.lower() else date_str.lower().split("autumn")[-1].strip()
            dt_object = dateutil_parser.parse(f"September 1, {year}")
        elif "winter" in date_str.lower():
            year = date_str.lower().split("winter")[-1].strip()
            dt_object = dateutil_parser.parse(f"December 1, {year}")
        else:
            dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e: # OverflowError for very large year numbers
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def process_washington_ag_breaches():
    """
    Fetches Washington AG security breach notifications, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting Washington AG Security Breach Notification processing...")

    final_url_to_scrape = WASHINGTON_AG_BREACH_INITIAL_URL
    try:
        # Perform a HEAD request first to resolve redirects and get the final URL
        head_response = requests.head(WASHINGTON_AG_BREACH_INITIAL_URL, headers=REQUEST_HEADERS, allow_redirects=True, timeout=15)
        head_response.raise_for_status()
        final_url_to_scrape = head_response.url
        logger.info(f"Initial URL '{WASHINGTON_AG_BREACH_INITIAL_URL}' resolved to '{final_url_to_scrape}'.")
        if not final_url_to_scrape.startswith("https://"):
            logger.warning(f"Final URL '{final_url_to_scrape}' is not HTTPS. Proceeding, but HTTPS is preferred.")

        response = requests.get(final_url_to_scrape, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Washington AG breach data page from {final_url_to_scrape}: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Washington AG site structure:
    # As of recent checks (2023-2024), data is typically in a <table>.
    # The table might be directly in the main content area, or within a specific div.
    # Example selector might be 'div.field-items table tbody tr' or similar.
    # We need to find the table and then iterate its rows.
    
    # Try to find a table - this is the most common structure historically.
    # Look for a table that seems to contain breach data. Often it might have specific headers.
    # A common pattern is tables within a div with class "content" or "main-content" or similar.
    data_table = None
    # First, try a more specific selector if known, e.g. based on a parent div
    # content_area = soup.find('div', class_='some-specific-class-if-known')
    # if content_area: data_table = content_area.find('table')
    
    # Generic search for tables if specific parent unknown
    if not data_table:
        all_tables = soup.find_all('table')
        if not all_tables:
            logger.error("No tables found on the page. The page structure might have changed, or it's not using tables for breach data anymore.")
            # logger.debug(f"Page content sample (first 1000 chars): {response.text[:1000]}")
            return

        # Heuristic: choose the largest table or one with expected headers.
        # For now, let's assume the first prominent table or a specific one if identifiable.
        # If multiple tables, this might need refinement.
        # Often, the data is in a table within a div with class "field-item" or "field-items"
        field_items_div = soup.find('div', class_=['field-item', 'field-items']) # Common Drupal class
        if field_items_div:
            data_table = field_items_div.find('table')
        
        if not data_table and all_tables:
            # Fallback: pick the first table found if no better heuristic. This might be fragile.
            data_table = all_tables[0] 
            logger.info(f"Found {len(all_tables)} table(s). Using the first one found as a fallback or the one within 'field-items'.")
        elif not data_table:
            logger.error("Could not identify a suitable data table within 'field-items' or as a primary table.")
            return


    if not data_table:
        logger.error("Failed to identify the data table containing breach notifications.")
        return

    tbody = data_table.find('tbody')
    if not tbody:
        logger.error("Table found, but it does not contain a <tbody> element. Cannot process rows.")
        return
        
    notifications = tbody.find_all('tr')
    logger.info(f"Found {len(notifications)} potential breach notifications in the table.")

    if not notifications:
        logger.warning("No rows found in the table body. The table might be empty or structured differently (e.g. no tbody).")
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

    # Determine column headers to map data correctly.
    # Assumes first row of table (or thead if present) contains headers.
    headers = []
    thead = data_table.find('thead')
    if thead:
        header_row = thead.find('tr')
        if header_row:
            headers = [th.get_text(strip=True).lower() for th in header_row.find_all(['th', 'td'])]
    
    if not headers and notifications: # Fallback: use first row of tbody if no thead
         first_row_cells = notifications[0].find_all(['th', 'td'])
         # Check if this looks like a header row (e.g. by inspecting content)
         # This part is heuristic. For now, we'll assume if thead is missing, direct data starts.
         logger.info("No <thead> found or no headers in <thead>. Will attempt to process rows assuming a fixed column order or rely on dynamic mapping if possible.")


    for row_idx, row in enumerate(notifications):
        processed_count += 1
        cols = row.find_all(['td', 'th']) # Include 'th' if data rows might use them for row headers (unlikely for WA AG)
        
        # Map columns to data fields based on headers if available and consistent
        # This mapping needs to be robust or adaptable if column order changes.
        # Example expected headers (actual headers can vary!):
        # "Date Posted", "Organization", "Date(s) of Breach", "Date AG Notified", "Description of Breach", "WA Residents Affected"
        # "Link to Notice"
        
        # Create a dictionary from the row cells and headers
        row_data = {}
        if headers:
            for i, cell in enumerate(cols):
                if i < len(headers):
                    row_data[headers[i]] = cell
        else: # No headers, rely on fixed column order (more fragile)
            # This part is highly dependent on the current structure of the WA AG site.
            # Let's assume a common order for now and log a warning.
            # 0: Organization Name, 1: Date Reported, 2: Date of Breach, ... (This is a GUESS)
            if len(cols) > 0: row_data['organization'] = cols[0] # Placeholder key
            if len(cols) > 1: row_data['date reported'] = cols[1] # Placeholder key
            if len(cols) > 2: row_data['dates of breach'] = cols[2] # Placeholder key
            if len(cols) > 3: row_data['description'] = cols[3] # Placeholder key
            if len(cols) > 4: row_data['wa residents affected'] = cols[4] # Placeholder key
            if len(cols) > 5: row_data['link to notice'] = cols[5] # Placeholder key
            if not headers:
                 logger.debug(f"Processing row {row_idx} without headers. Column count: {len(cols)}. Data: {[c.get_text(strip=True)[:50] for c in cols]}")


        # --- Extract data using flexible key matching (if headers were parsed) ---
        org_name_cell = row_data.get('organization name') or row_data.get('organization') or row_data.get('name of entity')
        date_reported_cell = row_data.get('date ag notified') or row_data.get('date reported') or row_data.get('date posted') or row_data.get('notice date')
        dates_breach_cell = row_data.get('date(s) of breach') or row_data.get('breach date(s)')
        description_cell = row_data.get('description of breach') or row_data.get('type of breach') or row_data.get('information compromised')
        residents_affected_cell = row_data.get('wa residents affected') or row_data.get('washingtonians affected') or row_data.get('residents affected')
        notice_link_cell = row_data.get('link to notice') or row_data.get('notice') or row_data.get('breach letter')

        # Get text and clean
        org_name = org_name_cell.get_text(strip=True) if org_name_cell else None
        date_reported_str = date_reported_cell.get_text(strip=True) if date_reported_cell else None
        dates_breach_str = dates_breach_cell.get_text(strip=True) if dates_breach_cell else None
        description = description_cell.get_text(strip=True) if description_cell else "Not specified"
        residents_affected_str = residents_affected_cell.get_text(strip=True) if residents_affected_cell else "Not specified"
        
        notice_link_tag = notice_link_cell.find('a', href=True) if notice_link_cell else None
        item_specific_url = None
        if notice_link_tag:
            item_specific_url = urljoin(final_url_to_scrape, notice_link_tag['href'])

        if not org_name or not date_reported_str:
            # If relying on fixed order and it's wrong, this might skip valid rows.
            logger.warning(f"Skipping row {row_idx+1} due to missing Organization Name ('{org_name}') or Date Reported ('{date_reported_str}'). Headers: {headers}. Col count: {len(cols)}. Row content: {[c.get_text(strip=True)[:30] for c in cols]}")
            skipped_count += 1
            continue

        publication_date_iso = parse_date_flexible_wa(date_reported_str)
        if not publication_date_iso:
            # Try parsing dates_breach_str if date_reported_str failed and might be a fallback
            publication_date_iso = parse_date_flexible_wa(dates_breach_str.split('-')[0].strip() if dates_breach_str else None) # Use start of range if applicable
            if not publication_date_iso:
                logger.warning(f"Skipping '{org_name}' due to unparsable primary date: Reported='{date_reported_str}', Breach='{dates_breach_str}'")
                skipped_count +=1
                continue
            else:
                logger.info(f"Used breach date as publication date for '{org_name}' as reported date was unparsable or missing.")


        raw_data = {
            "original_date_reported": date_reported_str,
            "dates_of_breach": dates_breach_str if dates_breach_str else "Not specified",
            "wa_residents_affected": residents_affected_str,
            "description_from_table": description,
            "original_notice_link": item_specific_url if item_specific_url else "Not provided on list page"
        }
        raw_data_json = {k: v for k, v in raw_data.items() if v is not None and v.strip().lower() not in ['n/a', 'unknown', '']}

        tags = ["washington_ag", "wa_breach"]
        if description and description.lower() != "not specified":
            # Simple tagging based on keywords in description
            desc_lower = description.lower()
            if "malware" in desc_lower: tags.append("malware")
            if "ransomware" in desc_lower: tags.append("ransomware")
            if "phishing" in desc_lower: tags.append("phishing")
            if "unauthorized access" in desc_lower: tags.append("unauthorized_access")
            if "email" in desc_lower: tags.append("email_compromise")


        item_data = {
            "source_id": SOURCE_ID_WASHINGTON_AG,
            "item_url": item_specific_url if item_specific_url else final_url_to_scrape,
            "title": org_name,
            "publication_date": publication_date_iso,
            "summary_text": description if description else "Details may be in linked notice if available.",
            "raw_data_json": raw_data_json,
            "tags_keywords": list(set(tags))
        }

        # TODO: Implement check for existing record before inserting
        # Example: Check by title and publication_date
        # query_result = supabase_client.client.table("scraped_items").select("id").eq("title", org_name).eq("publication_date", publication_date_iso).eq("source_id", SOURCE_ID_WASHINGTON_AG).execute()
        # if query_result.data:
        #     logger.info(f"Item '{org_name}' on {publication_date_iso} already exists. Skipping.")
        #     skipped_count +=1
        #     continue
            
        try:
            insert_response = supabase_client.insert_item(**item_data)
            if insert_response:
                logger.info(f"Successfully inserted item for '{org_name}'. URL: {item_data['item_url']}")
                inserted_count += 1
            else:
                logger.error(f"Failed to insert item for '{org_name}'. Supabase client returned no error, but no data in response.")
                # This case might indicate an issue with how insert_item signals success/failure
        except Exception as e_insert: # Catch specific Supabase errors if possible
            logger.error(f"Error inserting item for '{org_name}' into Supabase: {e_insert}", exc_info=True)
            # Potentially add to skipped_count here if appropriate

    logger.info(f"Finished processing Washington AG breaches. Total rows processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("Washington AG Security Breach Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_washington_ag_breaches()
        
    logger.info("Washington AG Security Breach Scraper Finished")
