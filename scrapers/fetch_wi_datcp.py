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
WISCONSIN_DATCP_BREACH_URL = "https://datcp.wi.gov/Pages/Programs_Services/DataBreaches.aspx"
SOURCE_ID_WISCONSIN_DATCP = 18

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_flexible_wi(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', 'ongoing', 'see letter', '']:
        return None
    try:
        # Example: "1/1/2023" or "January 1, 2023"
        dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def process_wisconsin_datcp_breaches():
    """
    Fetches Wisconsin DATCP data breach notices, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting Wisconsin DATCP Data Breach Notice processing...")

    try:
        response = requests.get(WISCONSIN_DATCP_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Wisconsin DATCP breach data page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Wisconsin DATCP site structure (datcp.wi.gov):
    # Data is typically within a main content area.
    # The page lists breaches, often grouped by year under accordion toggles or simple headers.
    # Example: <div class="accordion"> <h3>2023</h3> <div> <table>...</table> </div> </div>
    # Or just tables directly on the page if not many years.
    
    year_sections = []
    # Try to find accordion items first (common pattern for WI sites)
    # WI DATCP uses a specific accordion structure: <div class="WIThemeAccordion"> then <h3> for header, <div> for content.
    accordion_elements = soup.select("div.WIThemeAccordion") # This is the main container for all year accordions
    
    if accordion_elements:
        current_accordion_container = accordion_elements[0] # Usually just one main accordion container
        headers = current_accordion_container.find_all(['h3','h2']) # Year headers
        for header in headers:
            year_text = header.get_text(strip=True)
            # The content (table) is in the div immediately following the header
            content_div = header.find_next_sibling('div')
            if content_div:
                year_sections.append({'year_text': year_text, 'table_container': content_div})
    
    if not year_sections:
        # Fallback: Look for tables directly if no accordion structure found
        # Or simple hX + table structure
        all_tables = soup.find_all('table', class_=re.compile(r'table')) # Generic table search
        if all_tables:
            logger.info(f"No accordion sections found. Found {len(all_tables)} table(s) directly. Processing them.")
            for idx, table_el in enumerate(all_tables):
                # Try to find a preceding header for year context
                year_text_candidate = f"Table {idx+1} Data"
                prev_header = table_el.find_previous_sibling(['h2','h3','h4'])
                if prev_header:
                    year_match = re.search(r'(\d{4})', prev_header.get_text(strip=True))
                    if year_match: year_text_candidate = prev_header.get_text(strip=True)
                year_sections.append({'year_text': year_text_candidate, 'table_container': table_el})


    if not year_sections:
        logger.error("Could not find any year sections (accordion or direct tables) for breach notifications. Page structure might have changed.")
        # logger.debug(f"Page content sample (first 1000 chars): {response.text[:1000]}")
        return
        
    logger.info(f"Found {len(year_sections)} year sections/tables to process.")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    total_processed = 0
    total_inserted = 0
    total_skipped = 0
    
    for section in year_sections:
        year_text_full = section['year_text'] # e.g., "2023" or "2023 Data Breaches"
        table_container = section['table_container'] # This is the <div> containing table, or table itself
        
        data_table = table_container if table_container.name == 'table' else table_container.find('table')
        if not data_table:
            logger.warning(f"No table found in section '{year_text_full}'. Skipping this section.")
            continue
            
        tbody = data_table.find('tbody')
        if not tbody: 
            notifications = data_table.find_all('tr')
            if notifications and notifications[0].find_all('th'): # Simple check for header row
                notifications = notifications[1:]
        else:
            notifications = tbody.find_all('tr')

        if not notifications:
            logger.info(f"No breach notification rows found in table for section '{year_text_full}'.")
            continue
        
        year_for_tag = re.search(r'(\d{4})', year_text_full)
        year_for_tag = year_for_tag.group(1) if year_for_tag else "unknown_year"
        logger.info(f"Found {len(notifications)} potential breach notifications in section '{year_text_full}' (Year: {year_for_tag}).")
        
        page_processed_count = 0
        page_inserted_count = 0
        page_skipped_count = 0

        # Expected column order (inspect current site):
        # 0: Date Received (by DATCP)
        # 1: Organization Name
        # 2: Date(s) of Breach
        # 3: Number of WI Residents Affected (Optional)
        # 4: Link to Notice (Optional, may be on Org Name)

        for row_idx, row in enumerate(notifications):
            page_processed_count += 1
            cols = row.find_all('td')
            
            if len(cols) < 2: # Need at least Date Received and Org Name
                logger.warning(f"Skipping row {row_idx+1} in section '{year_text_full}' due to insufficient columns ({len(cols)}). Content: {[c.get_text(strip=True)[:30] for c in cols]}")
                page_skipped_count += 1
                continue

            try:
                date_received_str = cols[0].get_text(strip=True)
                org_name_cell = cols[1] # Cell might contain link
                org_name = org_name_cell.get_text(strip=True)
                
                item_specific_url = None
                link_in_org_name = org_name_cell.find('a', href=True)
                if link_in_org_name:
                    item_specific_url = urljoin(WISCONSIN_DATCP_BREACH_URL, link_in_org_name['href'])
                
                dates_of_breach_str = "Not specified"
                if len(cols) > 2:
                    dates_of_breach_str = cols[2].get_text(strip=True)
                
                residents_affected_str = "Not specified"
                if len(cols) > 3:
                    residents_affected_str = cols[3].get_text(strip=True)

                # Check if column 4 has a link if not found in org_name cell
                if not item_specific_url and len(cols) > 4:
                    link_in_col4 = cols[4].find('a', href=True)
                    if link_in_col4:
                        item_specific_url = urljoin(WISCONSIN_DATCP_BREACH_URL, link_in_col4['href'])


                if not org_name or not date_received_str:
                    logger.warning(f"Skipping row in '{year_text_full}' due to missing Org Name ('{org_name}') or Date Received ('{date_received_str}').")
                    page_skipped_count += 1
                    continue

                publication_date_iso = parse_date_flexible_wi(date_received_str)
                if not publication_date_iso:
                    # Fallback to date of breach if received date is not parsable
                    publication_date_iso = parse_date_flexible_wi(dates_of_breach_str.split('-')[0].strip() if dates_of_breach_str else None)
                    if not publication_date_iso:
                        logger.warning(f"Skipping '{org_name}' in '{year_text_full}' due to unparsable dates: Received='{date_received_str}', Breach='{dates_of_breach_str}'")
                        page_skipped_count +=1
                        continue
                    else:
                        logger.info(f"Used breach date as publication date for '{org_name}' in '{year_text_full}' as received date was unparsable/missing.")
                
                summary = f"Data breach at {org_name} reported to WI DATCP."
                if dates_of_breach_str and dates_of_breach_str.lower() not in ['n/a', 'unknown', 'pending', 'not specified']:
                    summary += f" Breach Date(s): {dates_of_breach_str}."
                if residents_affected_str and residents_affected_str.lower() not in ['n/a', 'unknown', 'pending', 'not specified'] and residents_affected_str.isdigit():
                    summary += f" WI Residents Affected: {residents_affected_str}."


                raw_data = {
                    "original_date_received_by_datcp": date_received_str,
                    "dates_of_breach": dates_of_breach_str,
                    "wi_residents_affected": residents_affected_str if residents_affected_str.isdigit() else "Not specified",
                    "year_section_on_page": year_text_full,
                    "original_notice_link": item_specific_url if item_specific_url else "Not provided on list page"
                }
                raw_data_json = {k: v for k, v in raw_data.items() if v is not None and str(v).strip().lower() not in ['n/a', 'unknown', '', 'pending', 'not specified']}

                tags = ["wisconsin_datcp", "wi_datcp", f"year_{year_for_tag}"]
                
                item_data = {
                    "source_id": SOURCE_ID_WISCONSIN_DATCP,
                    "item_url": item_specific_url if item_specific_url else WISCONSIN_DATCP_BREACH_URL,
                    "title": org_name,
                    "publication_date": publication_date_iso,
                    "summary_text": summary.strip(),
                    "raw_data_json": raw_data_json,
                    "tags_keywords": list(set(tags))
                }
                
                # TODO: Implement check for existing record before inserting

                insert_response = supabase_client.insert_item(**item_data)
                if insert_response:
                    logger.info(f"Successfully inserted item for '{org_name}' from section '{year_text_full}'. URL: {item_data['item_url']}")
                    page_inserted_count += 1
                else:
                    logger.error(f"Failed to insert item for '{org_name}' from section '{year_text_full}'.")

            except Exception as e:
                logger.error(f"Error processing row for '{org_name if 'org_name' in locals() else 'Unknown Entity'}' in section '{year_text_full}': {row.text[:150]}. Error: {e}", exc_info=True)
                page_skipped_count +=1
        
        total_processed += page_processed_count
        total_inserted += page_inserted_count
        total_skipped += page_skipped_count

    logger.info(f"Finished processing Wisconsin DATCP breaches. Total items processed: {total_processed}. Total items inserted: {total_inserted}. Total items skipped: {total_skipped}")

if __name__ == "__main__":
    logger.info("Wisconsin DATCP Data Breach Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_wisconsin_datcp_breaches()
        
    logger.info("Wisconsin DATCP Data Breach Scraper Finished")
