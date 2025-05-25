import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin

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
DELAWARE_AG_BREACH_URL = "https://attorneygeneral.delaware.gov/fraud/cpu/securitybreachnotification/database/"
SOURCE_ID_DELAWARE_AG = 3 # Placeholder for Delaware AG

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_delaware(date_str: str, formats: list = ["%m/%d/%Y", "%B %d, %Y"]) -> str | None:
    """
    Tries to parse a date string with a list of formats.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str:
        return None
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).isoformat()
        except ValueError:
            continue
    logger.warning(f"Could not parse date string: '{date_str}' with formats {formats}")
    return None

def process_delaware_ag_breaches():
    """
    Fetches Delaware AG security breach notifications, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting Delaware AG Security Breach Notification processing...")

    try:
        response = requests.get(DELAWARE_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Delaware AG breach data page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # The data is within a DataTable (no specific ID, but it's the main table on the page)
    # Look for the table containing breach data
    table = soup.find('table')
    if not table:
        logger.error("Could not find any table on the page. The page structure might have changed.")
        return

    tbody = table.find('tbody')
    if not tbody:
        logger.error("Could not find the table body (tbody) for breaches. Page structure might have changed.")
        return

    notifications = tbody.find_all('tr')
    logger.info(f"Found {len(notifications)} potential breach notifications on the page.")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    inserted_count = 0
    processed_count = 0
    skipped_count = 0

    for row in notifications:
        processed_count += 1
        cols = row.find_all('td')
        if len(cols) < 5: # Expecting at least 5 columns based on current table structure
            logger.warning(f"Skipping row due to insufficient columns ({len(cols)}): {row.text[:100]}")
            skipped_count += 1
            continue

        try:
            # Current column order (as of 2025):
            # 0: Organization Name
            # 1: Date(s) of Breach
            # 2: Reported Date (to AG)
            # 3: Number of Potentially Affected Delaware Residents
            # 4: Sample of Notice (contains PDF link)

            entity_name = cols[0].get_text(strip=True)
            date_of_breach_str = cols[1].get_text(strip=True)
            reported_date_str = cols[2].get_text(strip=True)
            residents_affected_text = cols[3].get_text(strip=True)

            # Link to detailed notice is in the 'Sample of Notice' column
            detailed_notice_link_tag = cols[4].find('a', href=True)
            item_specific_url = None
            if detailed_notice_link_tag:
                item_specific_url = urljoin(DELAWARE_AG_BREACH_URL, detailed_notice_link_tag['href'])

            if not entity_name:
                logger.warning(f"Skipping row due to missing entity name: {row.text[:100]}")
                skipped_count += 1
                continue

            # Prioritize reported date (to AG), then breach date for publication_date
            publication_date_iso = None
            if reported_date_str and reported_date_str.lower() not in ['n/a', 'unknown', '']:
                publication_date_iso = parse_date_delaware(reported_date_str)
            if not publication_date_iso and date_of_breach_str and date_of_breach_str.lower() not in ['n/a', 'unknown', '']:
                # Date of breach might be a range, take the start if so, or parse as single.
                # This simplistic parsing takes the first date found.
                publication_date_iso = parse_date_delaware(date_of_breach_str.split('–')[0].strip())  # Note: using en-dash

            if not publication_date_iso:
                 # If no valid date could be parsed, use a fallback or skip
                logger.warning(f"Skipping '{entity_name}' due to no parsable primary date. Reported: '{reported_date_str}', Breach: '{date_of_breach_str}'")
                skipped_count +=1
                continue


            raw_data = {
                "organization_name": entity_name,
                "date_of_breach": date_of_breach_str,
                "reported_date": reported_date_str,
                "delaware_residents_affected": residents_affected_text,
                "sample_notice_link": item_specific_url if item_specific_url else None
            }
            raw_data_json = {k: v for k, v in raw_data.items() if v is not None and v.strip() != "" and v.lower() != 'n/a'}

            # Create summary from available information
            summary = f"Breach reported on {reported_date_str}."
            if date_of_breach_str and date_of_breach_str.lower() != 'n/a':
                summary += f" Breach occurred: {date_of_breach_str}."
            if residents_affected_text and residents_affected_text.lower() != 'n/a':
                summary += f" DE Residents Affected: {residents_affected_text}."


            # Generate unique URL if no specific URL available
            if not item_specific_url:
                import urllib.parse
                org_slug = urllib.parse.quote(entity_name.replace(' ', '-').lower())
                date_slug = publication_date_iso.split('T')[0]  # Just the date part
                item_specific_url = f"{DELAWARE_AG_BREACH_URL}#{org_slug}-{date_slug}"

            item_data = {
                "source_id": SOURCE_ID_DELAWARE_AG,
                "item_url": item_specific_url,
                "title": entity_name,
                "publication_date": publication_date_iso,
                "summary_text": summary.strip(),
                "raw_data_json": raw_data_json,
                "tags_keywords": ["delaware_ag", "de_breach", "data_breach"]
            }

            # Check for existing record before inserting
            try:
                query_result = supabase_client.client.table("scraped_items").select("id").eq("title", entity_name).eq("publication_date", publication_date_iso).eq("source_id", SOURCE_ID_DELAWARE_AG).execute()
                if query_result.data:
                    logger.info(f"Item '{entity_name}' on {publication_date_iso} already exists. Skipping.")
                    skipped_count += 1
                    continue
            except Exception as e_check:
                logger.warning(f"Could not check for existing record: {e_check}. Proceeding with insert.")

            try:
                insert_response = supabase_client.insert_item(**item_data)
                if insert_response:
                    logger.info(f"Successfully inserted item for '{entity_name}'.")
                    inserted_count += 1
                else:
                    logger.error(f"Failed to insert item for '{entity_name}'.")
            except Exception as e_insert:
                if "duplicate key value violates unique constraint" in str(e_insert):
                    logger.info(f"Item '{entity_name}' already exists (duplicate URL). Skipping.")
                    skipped_count += 1
                else:
                    logger.error(f"Error inserting item for '{entity_name}' into Supabase: {e_insert}")
                    skipped_count += 1

        except Exception as e:
            logger.error(f"Error processing row for '{entity_name if 'entity_name' in locals() else 'Unknown Entity'}': {row.text[:150]}. Error: {e}", exc_info=True)
            skipped_count +=1

    logger.info(f"Finished processing Delaware AG breaches. Total rows processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("Delaware AG Security Breach Scraper Started")

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_delaware_ag_breaches()

    logger.info("Delaware AG Security Breach Scraper Finished")
