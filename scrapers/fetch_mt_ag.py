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
MONTANA_AG_BREACH_URL = "https://dojmt.gov/consumer/databreach/"
SOURCE_ID_MONTANA_AG = 12

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_flexible_mt(date_str: str) -> str | None:
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

def process_montana_ag_breaches():
    """
    Fetches Montana AG security breach notifications, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting Montana AG Security Breach Notification processing...")

    try:
        response = requests.get(MONTANA_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Montana AG breach data page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Montana AG site structure (dojmt.gov):
    # Data is typically within a main content area.
    # The page lists breaches by year, often under accordion-style toggles (e.g., "2023 Data Breaches").
    # Inside each year's section, there's usually a <table>.
    # Each row <tr> in that table is a breach.
    
    # Find all year sections/accordions. Common pattern is a div or similar element for each year.
    # Example: <div class="accordion-item"> <h2 class="accordion-header"><button>2023 Data Breaches</button></h2> <div class="accordion-collapse">...table here...</div></div>
    # Or could be simpler hX + table structure.
    
    year_sections = []
    # Try to find accordion items first (common pattern for DOJ sites)
    accordion_items = soup.select("div.accordion-item") # Bootstrap class
    if accordion_items:
        for item in accordion_items:
            header = item.find(['h2', 'h3', 'h4'], class_="accordion-header")
            body = item.find('div', class_="accordion-collapse")
            if header and body and header.find('button'):
                year_text = header.find('button').get_text(strip=True)
                year_sections.append({'year_text': year_text, 'table_container': body})
    
    if not year_sections:
        # Fallback: Look for hX tags with "YYYY Data Breaches" and assume table follows
        year_headers = soup.find_all(['h2', 'h3', 'h4'], string=re.compile(r'\d{4}\s+Data\s+Breaches', re.IGNORECASE))
        if year_headers:
            for header in year_headers:
                # Assume table is an immediate sibling or very close
                table = header.find_next_sibling('table')
                if not table: # Try one more level down if wrapped in a div
                    next_div = header.find_next_sibling('div')
                    if next_div: table = next_div.find('table')
                
                if table:
                    year_sections.append({'year_text': header.get_text(strip=True), 'table_container': table}) # Table itself is container
        else: # If no year headers, maybe there's just one main table on the page
            main_table = soup.find('table') # A very generic fallback
            if main_table:
                logger.info("No yearly sections found, attempting to process a single main table on the page.")
                year_sections.append({'year_text': "Current Page Data", 'table_container': main_table})


    if not year_sections:
        logger.error("Could not find any year sections or a main data table for breach notifications. Page structure might have changed.")
        # logger.debug(f"Page content sample (first 1000 chars): {response.text[:1000]}")
        return
        
    logger.info(f"Found {len(year_sections)} year sections to process.")

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
        year_text = section['year_text']
        table_container = section['table_container']
        
        data_table = table_container if table_container.name == 'table' else table_container.find('table')
        if not data_table:
            logger.warning(f"No table found in section '{year_text}'. Skipping this section.")
            continue
            
        tbody = data_table.find('tbody')
        if not tbody: 
            notifications = data_table.find_all('tr')
            if notifications and notifications[0].find_all('th'): # Simple check for header row
                notifications = notifications[1:]
        else:
            notifications = tbody.find_all('tr')

        if not notifications:
            logger.info(f"No breach notification rows found in table for section '{year_text}'.")
            continue
        
        logger.info(f"Found {len(notifications)} potential breach notifications in section '{year_text}'.")
        
        page_processed_count = 0
        page_inserted_count = 0
        page_skipped_count = 0

        # Expected column order (can vary, inspect current site):
        # 0: Name of Entity
        # 1: Date(s) of Breach
        # 2: Date Reported to Consumers/OCR (Office of Consumer Protection)
        # 3: Type of Information
        # 4: Link to Notice (Optional)

        for row_idx, row in enumerate(notifications):
            page_processed_count += 1
            cols = row.find_all('td')
            
            if len(cols) < 3: # Need at least Entity, Breach Date, Reported Date
                logger.warning(f"Skipping row {row_idx+1} in section '{year_text}' due to insufficient columns ({len(cols)}). Content: {[c.get_text(strip=True)[:30] for c in cols]}")
                page_skipped_count += 1
                continue

            try:
                entity_name = cols[0].get_text(strip=True)
                dates_of_breach_str = cols[1].get_text(strip=True)
                date_reported_str = cols[2].get_text(strip=True) # Date reported to Consumers/OCR
                
                type_of_info = "Not specified"
                if len(cols) > 3:
                    type_of_info = cols[3].get_text(strip=True)

                notice_link_tag = None
                if len(cols) > 4:
                     notice_link_tag = cols[4].find('a', href=True)
                
                item_specific_url = None
                if notice_link_tag:
                    item_specific_url = urljoin(MONTANA_AG_BREACH_URL, notice_link_tag['href'])

                if not entity_name or not date_reported_str:
                    logger.warning(f"Skipping row in '{year_text}' due to missing Entity Name ('{entity_name}') or Date Reported ('{date_reported_str}').")
                    page_skipped_count += 1
                    continue

                publication_date_iso = parse_date_flexible_mt(date_reported_str)
                if not publication_date_iso:
                    # Fallback to date of breach if reported date is not parsable
                    publication_date_iso = parse_date_flexible_mt(dates_of_breach_str.split('-')[0].strip() if dates_of_breach_str else None)
                    if not publication_date_iso:
                        logger.warning(f"Skipping '{entity_name}' in '{year_text}' due to unparsable dates: Reported='{date_reported_str}', Breach='{dates_of_breach_str}'")
                        page_skipped_count +=1
                        continue
                    else:
                        logger.info(f"Used breach date as publication date for '{entity_name}' in '{year_text}' as reported date was unparsable/missing.")
                
                summary = f"Security breach reported by {entity_name}."
                if dates_of_breach_str and dates_of_breach_str.lower() not in ['n/a', 'unknown', 'pending']:
                    summary += f" Breach occurred around: {dates_of_breach_str}."
                if type_of_info and type_of_info.lower() not in ['n/a', 'unknown', 'pending', 'not specified', '']:
                    summary += f" Type of Information: {type_of_info}."

                raw_data = {
                    "original_date_reported_to_consumers_ocr": date_reported_str,
                    "dates_of_breach": dates_of_breach_str,
                    "type_of_information": type_of_info,
                    "year_section_on_page": year_text,
                    "original_notice_link": item_specific_url if item_specific_url else "Not provided in this row"
                }
                raw_data_json = {k: v for k, v in raw_data.items() if v is not None and str(v).strip().lower() not in ['n/a', 'unknown', '', 'pending', 'not specified']}

                tags = ["montana_ag", "mt_ag"]
                year_match_tag = re.search(r'(\d{4})', year_text) # Extract year from section title for tag
                if year_match_tag: tags.append(f"year_{year_match_tag.group(1)}")
                
                # Basic tagging from type of info
                if type_of_info:
                    toi_lower = type_of_info.lower()
                    if "ssn" in toi_lower or "social security" in toi_lower: tags.append("ssn_compromised")
                    if "financial" in toi_lower or "payment card" in toi_lower or "bank account" in toi_lower: tags.append("financial_info_compromised")
                    if "driver's license" in toi_lower or "driver license" in toi_lower : tags.append("drivers_license_compromised")


                item_data = {
                    "source_id": SOURCE_ID_MONTANA_AG,
                    "item_url": item_specific_url if item_specific_url else MONTANA_AG_BREACH_URL,
                    "title": entity_name,
                    "publication_date": publication_date_iso,
                    "summary_text": summary.strip(),
                    "raw_data_json": raw_data_json,
                    "tags_keywords": list(set(tags))
                }
                
                # TODO: Implement check for existing record before inserting

                insert_response = supabase_client.insert_item(**item_data)
                if insert_response:
                    logger.info(f"Successfully inserted item for '{entity_name}' from section '{year_text}'. URL: {item_data['item_url']}")
                    page_inserted_count += 1
                else:
                    logger.error(f"Failed to insert item for '{entity_name}' from section '{year_text}'.")

            except Exception as e:
                logger.error(f"Error processing row for '{entity_name if 'entity_name' in locals() else 'Unknown Entity'}' in section '{year_text}': {row.text[:150]}. Error: {e}", exc_info=True)
                page_skipped_count +=1
        
        total_processed += page_processed_count
        total_inserted += page_inserted_count
        total_skipped += page_skipped_count

    logger.info(f"Finished processing Montana AG breaches. Total items processed: {total_processed}. Total items inserted: {total_inserted}. Total items skipped: {total_skipped}")

if __name__ == "__main__":
    logger.info("Montana AG Security Breach Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_montana_ag_breaches()
        
    logger.info("Montana AG Security Breach Scraper Finished")
