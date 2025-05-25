import os
import logging
import requests
import csv
import io
from datetime import datetime

# Assuming SupabaseClient is in utils.supabase_client
# Adjust the import path if your project structure is different
try:
    from utils.supabase_client import SupabaseClient
except ImportError:
    # This is to allow the script to be run directly for testing
    # without having the utils package installed in the traditional sense.
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from utils.supabase_client import SupabaseClient

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
HHS_OCR_CSV_DOWNLOAD_URL = "https://ocrportal.hhs.gov/ocr/breach/breach_report.jsf?download=true"
# Placeholder for the source_id from the 'data_sources' table in Supabase
# This ID should correspond to "HHS OCR Breach Portal"
SOURCE_ID_HHS_OCR = 2

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date(date_str: str, formats: list = ["%m/%d/%Y"]) -> str | None:
    """
    Tries to parse a date string with a list of formats.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str:
        return None
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).isoformat()
        except ValueError:
            continue
    logger.warning(f"Could not parse date string: {date_str} with formats {formats}")
    return None

def process_hhs_ocr_csv():
    """
    Fetches the HHS OCR breach data as CSV, processes each record,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting HHS OCR Breach Report CSV processing...")

    try:
        response = requests.get(HHS_OCR_CSV_DOWNLOAD_URL, headers=REQUEST_HEADERS, timeout=60)
        response.raise_for_status()  # Raise an exception for HTTP errors
        # The content is binary, decode it to utf-8, common for CSVs from web sources
        # Some sources might use other encodings like 'latin-1' or 'cp1252'
        # If encoding issues arise, chardet library could be used to detect it.
        csv_content = response.content.decode('utf-8-sig') # utf-8-sig handles potential BOM
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching HHS OCR CSV data: {e}")
        return
    except UnicodeDecodeError as e:
        logger.error(f"Error decoding CSV content: {e}. Trying 'latin-1'.")
        try:
            csv_content = response.content.decode('latin-1')
        except UnicodeDecodeError as e_latin1:
            logger.error(f"Error decoding CSV content with 'latin-1': {e_latin1}. Aborting.")
            return


    csvfile = io.StringIO(csv_content)
    reader = csv.DictReader(csvfile)

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    inserted_count = 0
    processed_count = 0
    skipped_count = 0

    for row in reader:
        processed_count += 1
        try:
            name_of_covered_entity = row.get("Name of Covered Entity")
            breach_submission_date_str = row.get("Breach Submission Date") # Format: "12/12/2023"
            individuals_affected_str = row.get("Individuals Affected")
            type_of_breach = row.get("Type of Breach") # e.g., "Hacking/IT Incident"
            location_of_breached_info = row.get("Location of Breached Information") # e.g., "Network Server"

            if not name_of_covered_entity or not breach_submission_date_str:
                logger.warning(f"Skipping row due to missing Name of Covered Entity or Breach Submission Date: {row}")
                skipped_count +=1
                continue

            publication_date_iso = parse_date(breach_submission_date_str)
            if not publication_date_iso:
                logger.warning(f"Skipping row for '{name_of_covered_entity}' due to unparsable date: {breach_submission_date_str}")
                skipped_count +=1
                continue
            
            # Construct a pseudo-unique URL if none is directly available.
            # This is tricky without a true unique ID per breach in the CSV.
            # One approach is to use the main portal URL and append some row data,
            # but this isn't a stable link to a specific breach report.
            # For now, we can use the entity name and date as part of a reference,
            # or leave item_url as None if no clear unique identifier for a URL exists.
            # A better approach might be to use a hash of key row data if we need a unique ID for item_url.
            item_url_slug = f"{name_of_covered_entity.replace(' ', '-').lower()}-{publication_date_iso}"
            item_url = f"https://ocrportal.hhs.gov/ocr/breach/breach_report.jsf#details-{item_url_slug}" # Example, not a real link

            # Prepare data for Supabase
            raw_data = {
                "name_of_covered_entity": name_of_covered_entity,
                "state": row.get("State"),
                "covered_entity_type": row.get("Covered Entity Type"),
                "individuals_affected": int(individuals_affected_str) if individuals_affected_str and individuals_affected_str.isdigit() else None,
                "breach_submission_date": breach_submission_date_str, # Original date string
                "type_of_breach": type_of_breach,
                "location_of_breached_information": location_of_breached_info,
                "business_associate_present": row.get("Business Associate Present"),
                "web_description": row.get("Web Description"), # Often empty or very brief
                # Include any other columns you find relevant
                "year_of_breach": breach_submission_date_str.split('/')[-1] if breach_submission_date_str else None
            }
             # Remove keys where value is None from raw_data to keep it clean
            raw_data_json = {k: v for k, v in raw_data.items() if v is not None and v != ""}


            tags = ["hhs_ocr", "healthcare_breach"]
            if type_of_breach:
                tags.append(type_of_breach.lower().replace("/", "_").replace(" ", "_"))
            if raw_data.get("business_associate_present", "").lower() == "yes":
                tags.append("business_associate_involved")


            item_data = {
                "source_id": SOURCE_ID_HHS_OCR,
                "item_url": item_url, # Or None if a meaningful URL cannot be constructed
                "title": name_of_covered_entity,
                "publication_date": publication_date_iso,
                "summary_text": f"Type: {type_of_breach}. Location: {location_of_breached_info}.",
                "full_content": row.get("Web Description"), # Or concatenate more fields if desired
                "raw_data_json": raw_data_json,
                "tags_keywords": list(set(tags)) # Ensure unique tags
            }

            # TODO: Implement check for existing record before inserting to avoid duplicates.
            # This could be a query like:
            # exists = supabase_client.client.table("scraped_items") \
            # .select("id") \
            # .eq("title", name_of_covered_entity) \
            # .eq("publication_date", publication_date_iso) \
            # .eq("source_id", SOURCE_ID_HHS_OCR) \
            # .execute()
            # if not exists.data:
            #    insert_response = supabase_client.insert_item(**item_data) ...
            # else:
            #    logger.info(f"Item already exists for {name_of_covered_entity} on {publication_date_iso}. Skipping.")

            insert_response = supabase_client.insert_item(**item_data)
            if insert_response:
                logger.info(f"Successfully inserted item for '{name_of_covered_entity}'.")
                inserted_count += 1
            else:
                logger.error(f"Failed to insert item for '{name_of_covered_entity}'.")

        except Exception as e:
            logger.error(f"Error processing row: {row}. Error: {e}", exc_info=True)
            skipped_count +=1

    logger.info(f"Finished processing HHS OCR CSV. Total rows processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("HHS OCR Breach Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_hhs_ocr_csv()
        
    logger.info("HHS OCR Breach Scraper Finished")
