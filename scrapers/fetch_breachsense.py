import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin, unquote
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
BREACHSENSE_URL = "https://www.breachsense.com/breaches/"
SOURCE_ID_BREACHSENSE = 19

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_flexible_bs(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', 'ongoing', 'see letter', '']:
        return None
    try:
        # Example: "January 1, 2023" or "1/1/2023"
        dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def process_breachsense_breaches():
    """
    Fetches BreachSense breach listings, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting BreachSense Breach Notification processing...")

    try:
        response = requests.get(BREACHSENSE_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
        logger.info(f"Successfully fetched BreachSense page. Content length: {len(response.text)} bytes.")
        if len(response.text) < 10000: # Arbitrary check for very short content
            logger.warning("Fetched page content is very short, which might indicate dynamic loading not captured by requests. Further inspection or headless browser might be needed if data is missing.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching BreachSense breach data page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # BreachSense site structure (www.breachsense.com/breaches/):
    # As of early 2024, breaches are listed in a table-like structure.
    # Each breach is a <tr> within a <tbody> of a table with class "table table-sm".
    # Columns are typically: Date, Organization, Records, Data Types, Source (Link)
    
    data_table = soup.find('table', class_="table-sm") # Class "table table-sm"
    if not data_table:
        # Fallback: try any table if the specific class is not found
        data_table = soup.find('table')
        if not data_table:
            logger.error("Could not find the data table (e.g., with class 'table-sm'). Page structure might have changed or content is JS-loaded.")
            # logger.debug(f"Page content sample (first 1000 chars): {response.text[:1000]}")
            return
        else:
            logger.info("Found a generic table. Assuming this is the breach data table.")
            
    tbody = data_table.find('tbody')
    if not tbody:
        # If no tbody, check if rows are directly under table
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
    # 0: Date (of breach or reporting)
    # 1: Organization
    # 2: Records (affected count)
    # 3: Data Types (compromised)
    # 4: Source (Link to source/article)

    for row_idx, row in enumerate(notifications):
        processed_count += 1
        cols = row.find_all('td')
        
        if len(cols) < 4: # Need at least Date, Org, Records, Data Types. Source is optional but expected.
            logger.warning(f"Skipping row {row_idx+1} due to insufficient columns ({len(cols)}). Content: {[c.get_text(strip=True)[:30] for c in cols]}")
            skipped_count += 1
            continue

        try:
            date_str = cols[0].get_text(strip=True)
            org_name = cols[1].get_text(strip=True)
            records_affected_str = cols[2].get_text(strip=True) # e.g., "1.5M", "Unknown"
            data_types_str = cols[3].get_text(strip=True)
            
            source_link_tag = None
            item_specific_url = None
            if len(cols) > 4:
                source_link_tag = cols[4].find('a', href=True)
                if source_link_tag:
                    item_specific_url = urljoin(BREACHSENSE_URL, source_link_tag['href'])
                    # Check if link is to an actual source or just a generic internal link
                    if "breachsense.com" in item_specific_url and not source_link_tag.get_text(strip=True).lower() not in ["source", "link", "details"]:
                         # If it links back to breachsense itself without specific text, might not be the primary source link
                         pass # Keep it for now, but good to be aware

            if not org_name or not date_str:
                logger.warning(f"Skipping row due to missing Organization Name ('{org_name}') or Date ('{date_str}').")
                skipped_count += 1
                continue

            publication_date_iso = parse_date_flexible_bs(date_str)
            if not publication_date_iso:
                logger.warning(f"Skipping '{org_name}' due to unparsable date: '{date_str}'")
                skipped_count +=1
                continue
                
            summary = f"Data breach at {org_name}."
            if data_types_str and data_types_str.lower() != 'unknown':
                summary += f" Data types compromised: {data_types_str}."
            if records_affected_str and records_affected_str.lower() != 'unknown':
                summary += f" Records affected: {records_affected_str}."


            # Clean up records_affected_str for storage if it's like "1.5M" -> 1500000
            # This is a simple conversion, more robust parsing might be needed for various formats.
            records_affected_numeric = None
            if records_affected_str:
                val_lower = records_affected_str.lower()
                if 'm' in val_lower:
                    try: records_affected_numeric = int(float(val_lower.replace('m', '')) * 1_000_000)
                    except ValueError: pass
                elif 'k' in val_lower:
                    try: records_affected_numeric = int(float(val_lower.replace('k', '')) * 1_000)
                    except ValueError: pass
                elif val_lower.isdigit():
                    try: records_affected_numeric = int(val_lower)
                    except ValueError: pass
                # Else, it might be "Unknown" or some other text, keep as original string for raw_data.

            raw_data = {
                "original_date_string": date_str,
                "records_affected_original_string": records_affected_str,
                "records_affected_numeric": records_affected_numeric if records_affected_numeric is not None else "Not specified/Unknown",
                "data_types_compromised": data_types_str,
                "source_link_from_breachsense": item_specific_url if item_specific_url else "Not provided"
            }
            raw_data_json = {k: v for k, v in raw_data.items() if v is not None and str(v).strip().lower() not in ['n/a', 'unknown', '', 'pending', 'not specified']}

            tags = ["breachsense", "data_leak"]
            if data_types_str:
                # Create tags from data types, e.g., "Email, Password" -> ["email", "password"]
                data_type_tags = [dt.strip().lower().replace(" ", "_") for dt in data_types_str.split(',')]
                tags.extend(data_type_tags)
            
            # Add tag based on scale of breach if numeric records available
            if records_affected_numeric is not None:
                if records_affected_numeric >= 1_000_000: tags.append("large_scale_breach")
                elif records_affected_numeric >= 100_000: tags.append("medium_scale_breach")


            item_data = {
                "source_id": SOURCE_ID_BREACHSENSE,
                "item_url": item_specific_url if item_specific_url else BREACHSENSE_URL, # Use BreachSense URL if no specific source
                "title": org_name,
                "publication_date": publication_date_iso,
                "summary_text": summary.strip(),
                "raw_data_json": raw_data_json,
                "tags_keywords": list(set(tags)) # Ensure unique tags
            }
            
            # TODO: Implement check for existing record before inserting (e.g., by title and date)

            insert_response = supabase_client.insert_item(**item_data)
            if insert_response:
                logger.info(f"Successfully inserted item for '{org_name}'. URL: {item_data['item_url']}")
                inserted_count += 1
            else:
                logger.error(f"Failed to insert item for '{org_name}'.")

        except Exception as e:
            logger.error(f"Error processing row for '{org_name if 'org_name' in locals() else 'Unknown Entity'}': {row.text[:150]}. Error: {e}", exc_info=True)
            skipped_count +=1

    logger.info(f"Finished processing BreachSense breaches. Total items processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("BreachSense Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_breachsense_breaches()
        
    logger.info("BreachSense Scraper Finished")
