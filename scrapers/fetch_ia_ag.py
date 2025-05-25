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
IOWA_AG_BREACH_URL = "https://www.iowaattorneygeneral.gov/for-consumers/security-breach-notifications/"
SOURCE_ID_IOWA_AG = 8

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_flexible_ia(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', 'ongoing']:
        return None
    try:
        dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def process_iowa_ag_breaches():
    """
    Fetches Iowa AG security breach notifications, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting Iowa AG Security Breach Notification processing...")

    try:
        response = requests.get(IOWA_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Iowa AG breach data page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Iowa AG site structure:
    # Notifications are usually within a main content area.
    # The page lists breaches by year, with links to PDFs or detail pages.
    # Each year is often a section, and breaches are list items or table rows.
    # As of inspection (early 2024), it's a list of accordions (one for each year).
    # Inside each accordion body (div.accordion-body), there's a <table>.
    # Each row <tr> in that table is a breach.
    
    # Find all accordion bodies, which should contain the tables for each year.
    accordion_bodies = soup.select("div.accordion-body") # Bootstrap accordion selector
    
    if not accordion_bodies:
        logger.error("Could not find accordion bodies for breach notifications. Page structure might have changed.")
        # logger.debug(f"Page content sample (first 1000 chars): {response.text[:1000]}")
        return
        
    logger.info(f"Found {len(accordion_bodies)} accordion sections (likely years).")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    inserted_count = 0
    processed_count = 0
    skipped_count = 0
    
    # Year might be extractable from accordion header (e.g., button.accordion-button text)
    # For now, we'll parse dates directly from table cells.

    for body_idx, accordion_body in enumerate(accordion_bodies):
        year_text_from_header = "Unknown Year"
        accordion_button = accordion_body.find_previous_sibling('h2', class_='accordion-header')
        if accordion_button and accordion_button.find('button'):
            year_text_from_header = accordion_button.find('button').get_text(strip=True)
            logger.info(f"Processing accordion section: {year_text_from_header}")

        data_table = accordion_body.find('table')
        if not data_table:
            logger.warning(f"No table found in accordion body #{body_idx+1} ({year_text_from_header}). Skipping this section.")
            continue
            
        tbody = data_table.find('tbody')
        if not tbody: # Some tables might just have <tr> directly under <table>
            notifications = data_table.find_all('tr')
            # Remove header row if present (first <tr> with <th>)
            if notifications and notifications[0].find_all('th'):
                notifications = notifications[1:]
        else:
            notifications = tbody.find_all('tr')

        if not notifications:
            logger.info(f"No breach notification rows found in table for section '{year_text_from_header}'.")
            continue
        
        logger.info(f"Found {len(notifications)} potential breach notifications in section '{year_text_from_header}'.")

        # Expected column order (can vary):
        # 0: Date Notified Iowa AG (or Date Posted)
        # 1: Company Name (may contain link to notice)
        # 2: Date(s) of Breach
        # 3: Iowa Residents Affected (Optional)

        for row_idx, row in enumerate(notifications):
            processed_count += 1
            cols = row.find_all('td')
            
            if len(cols) < 2: # Need at least Date Notified and Company Name
                logger.warning(f"Skipping row {row_idx+1} in section '{year_text_from_header}' due to insufficient columns ({len(cols)}). Content: {[c.get_text(strip=True)[:30] for c in cols]}")
                skipped_count += 1
                continue

            try:
                date_notified_ag_str = cols[0].get_text(strip=True)
                company_name_cell = cols[1] # Cell might contain link
                company_name = company_name_cell.get_text(strip=True)
                
                notice_link_tag = company_name_cell.find('a', href=True)
                item_specific_url = None
                if notice_link_tag:
                    item_specific_url = urljoin(IOWA_AG_BREACH_URL, notice_link_tag['href'])
                    # Clean company name if link text is just "Notice" or similar
                    if company_name.lower() in ["notice", "notification", "letter", "view notice"]:
                         # This happens if the entire cell is the link with generic text.
                         # We might need a better way to get company name if this occurs.
                         # For now, if PDF filename is descriptive, use that.
                         if item_specific_url and item_specific_url.lower().endswith(".pdf"):
                             pdf_name = os.path.basename(item_specific_url).split('.')[0]
                             company_name = pdf_name.replace('_', ' ').replace('-', ' ').title()
                         else: # Fallback to a generic name or skip
                             company_name = f"Unknown Company (Link Text: {company_name_cell.get_text(strip=True)})"


                dates_of_breach_str = cols[2].get_text(strip=True) if len(cols) > 2 else "Not specified"
                residents_affected_str = cols[3].get_text(strip=True) if len(cols) > 3 else "Not specified"


                if not company_name or company_name.startswith("Unknown Company") or not date_notified_ag_str:
                    logger.warning(f"Skipping row in '{year_text_from_header}' due to missing Company Name ('{company_name}') or Date Notified AG ('{date_notified_ag_str}').")
                    skipped_count += 1
                    continue

                publication_date_iso = parse_date_flexible_ia(date_notified_ag_str)
                if not publication_date_iso:
                    # Try parsing dates_of_breach_str if primary date failed
                    publication_date_iso = parse_date_flexible_ia(dates_of_breach_str.split('-')[0].strip() if dates_of_breach_str else None)
                    if not publication_date_iso:
                        logger.warning(f"Skipping '{company_name}' in '{year_text_from_header}' due to unparsable dates: Notified='{date_notified_ag_str}', Breach='{dates_of_breach_str}'")
                        skipped_count +=1
                        continue
                    else:
                        logger.info(f"Used breach date as publication date for '{company_name}' in '{year_text_from_header}' as notified date was unparsable/missing.")
                

                summary = f"Security breach notification for {company_name}."
                if dates_of_breach_str and dates_of_breach_str.lower() != 'not specified':
                    summary += f" Breach occurred around: {dates_of_breach_str}."
                if residents_affected_str and residents_affected_str.lower() != 'not specified':
                    summary += f" Iowa Residents Affected: {residents_affected_str}."

                raw_data = {
                    "original_date_notified_ag": date_notified_ag_str,
                    "dates_of_breach": dates_of_breach_str,
                    "iowa_residents_affected": residents_affected_str,
                    "year_section_on_page": year_text_from_header,
                    "original_notice_link": item_specific_url if item_specific_url else "Not provided in this row"
                }
                raw_data_json = {k: v for k, v in raw_data.items() if v is not None and v.strip().lower() not in ['n/a', 'unknown', '', 'not specified']}

                tags = ["iowa_ag", "ia_breach"]
                # Further tags could be added if notice content was fetched and parsed.


                item_data = {
                    "source_id": SOURCE_ID_IOWA_AG,
                    "item_url": item_specific_url if item_specific_url else IOWA_AG_BREACH_URL,
                    "title": company_name,
                    "publication_date": publication_date_iso,
                    "summary_text": summary,
                    "raw_data_json": raw_data_json,
                    "tags_keywords": list(set(tags))
                }
                
                # TODO: Implement check for existing record before inserting

                insert_response = supabase_client.insert_item(**item_data)
                if insert_response:
                    logger.info(f"Successfully inserted item for '{company_name}' from section '{year_text_from_header}'. URL: {item_data['item_url']}")
                    inserted_count += 1
                else:
                    logger.error(f"Failed to insert item for '{company_name}' from section '{year_text_from_header}'.")

            except Exception as e:
                logger.error(f"Error processing row for '{company_name if 'company_name' in locals() else 'Unknown Company'}' in section '{year_text_from_header}': {row.text[:150]}. Error: {e}", exc_info=True)
                skipped_count +=1

    logger.info(f"Finished processing Iowa AG breaches. Total items processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("Iowa AG Security Breach Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_iowa_ag_breaches()
        
    logger.info("Iowa AG Security Breach Scraper Finished")
