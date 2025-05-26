import os
import logging
import requests
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
CISA_KEV_JSON_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
SOURCE_ID_CISA_KEV = 37
CVE_ORG_BASE_URL = "https://www.cve.org/CVERecord?id="

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/json'
}

def parse_date_cisa_kev(date_str: str) -> str | None:
    """
    Parses date string (YYYY-MM-DD) from CISA KEV to ISO 8601 format.
    """
    if not date_str:
        return None
    try:
        # dateutil.parser can handle "YYYY-MM-DD" directly
        dt_object = dateutil_parser.parse(date_str)
        return dt_object.isoformat()
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not parse date string from CISA KEV: '{date_str}'. Error: {e}")
        return None

def process_cisa_kev_vulnerabilities():
    """
    Fetches Known Exploited Vulnerabilities (KEV) from CISA's JSON feed
    and inserts them into Supabase.
    """
    logger.info("Starting CISA Known Exploited Vulnerabilities (KEV) processing...")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    try:
        response = requests.get(CISA_KEV_JSON_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status() # Raise an exception for bad status codes

        kev_data_full = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data from CISA KEV JSON feed ({CISA_KEV_JSON_URL}): {e}", exc_info=True)
        return
    except ValueError as e_json: # Includes JSONDecodeError
        logger.error(f"Error decoding JSON response from CISA KEV feed ({CISA_KEV_JSON_URL}): {e_json}. Response text: {response.text[:500]}")
        return

    # The JSON structure has a top-level key, often "vulnerabilities" or similar.
    # Let's inspect the structure or assume a common one.
    # Based on CISA's documentation, it's usually:
    # { "title": "...", "catalogVersion": "...", "dateReleased": "...", "count": X, "vulnerabilities": [...] }

    vulnerabilities_list = kev_data_full.get("vulnerabilities")
    if vulnerabilities_list is None: # Handle if the key name changes or is missing
        # Try to find a list among the values if the structure is flat or key is unknown
        for key, value in kev_data_full.items():
            if isinstance(value, list) and value: # Take the first non-empty list found
                # Check if items in list look like vulnerabilities (e.g., have 'cveID')
                if isinstance(value[0], dict) and "cveID" in value[0]:
                    vulnerabilities_list = value
                    logger.info(f"Found vulnerabilities list under an unexpected key '{key}'. Proceeding.")
                    break
        if vulnerabilities_list is None:
            logger.error(f"Could not find the 'vulnerabilities' list in the JSON response from CISA KEV. Keys found: {list(kev_data_full.keys())}")
            return

    if not vulnerabilities_list:
        logger.info("No vulnerabilities found in the CISA KEV data.")
        return

    logger.info(f"Successfully fetched and parsed {len(vulnerabilities_list)} KEV entries from CISA.")

    inserted_count = 0
    processed_count = 0
    skipped_count = 0

    for kev_entry in vulnerabilities_list:
        processed_count += 1
        try:
            cve_id = kev_entry.get("cveID")
            vendor_project = kev_entry.get("vendorProject")
            product = kev_entry.get("product")
            vulnerability_name = kev_entry.get("vulnerabilityName")
            date_added_str = kev_entry.get("dateAdded") # Date added to KEV catalog
            short_description = kev_entry.get("shortDescription")
            required_action = kev_entry.get("requiredAction")
            due_date_str = kev_entry.get("dueDate") # Due date for federal agencies
            notes = kev_entry.get("notes")

            if not cve_id or not vulnerability_name or not date_added_str:
                logger.warning(f"Skipping KEV entry due to missing cveID, vulnerabilityName, or dateAdded. Entry: {kev_entry}")
                skipped_count += 1
                continue

            # Construct item_url using CVE.org for vulnerability details
            item_url = urljoin(CVE_ORG_BASE_URL, cve_id)

            title = f"CISA KEV: {cve_id} - {vulnerability_name}"
            if product and product.lower() not in vulnerability_name.lower(): # Add product if not redundant
                title = f"CISA KEV: {cve_id} - {product} - {vulnerability_name}"


            publication_date_iso = parse_date_cisa_kev(date_added_str)
            if not publication_date_iso:
                logger.warning(f"Skipping KEV entry for '{cve_id}' due to unparsable dateAdded: '{date_added_str}'.")
                skipped_count +=1
                continue

            due_date_iso = parse_date_cisa_kev(due_date_str) # Optional, might be null

            raw_data = {
                "cve_id": cve_id,
                "vendor_project": vendor_project,
                "product": product,
                "vulnerability_name_original": vulnerability_name, # Store original name from KEV
                "required_action": required_action,
                "due_date_kev": due_date_iso,
                "notes_kev": notes if notes else None # Ensure None if empty/null from source
            }
            # Clean None values from raw_data
            raw_data_json = {k: v for k, v in raw_data.items() if v is not None}


            tags = ["cisa_kev", "vulnerability", "exploited"]
            if vendor_project: tags.append(vendor_project.lower().replace(" ", "_").replace("-","_"))
            if product: tags.append(product.lower().replace(" ", "_").replace("-","_"))
            # Add CVE year as a tag if useful, e.g., cve_2023
            if cve_id and cve_id.startswith("CVE-"):
                try: tags.append(f"cve_{cve_id.split('-')[1]}")
                except IndexError: pass # In case CVE format is unexpected

            tags = list(set(tags)) # Ensure unique tags


            item_data = {
                "source_id": SOURCE_ID_CISA_KEV,
                "item_url": item_url,
                "title": title,
                "publication_date": publication_date_iso,
                "summary_text": short_description,
                "raw_data_json": raw_data_json,
                "tags_keywords": tags
            }

            # TODO: Implement check for existing record before inserting (e.g., by cve_id in raw_data_json and source_id)
            # Example: query_result = supabase_client.client.table("scraped_items").select("id").eq("raw_data_json->>cve_id", cve_id).eq("source_id", SOURCE_ID_CISA_KEV).execute()
            # if query_result.data: logger.info(f"CISA KEV item for '{cve_id}' already exists. Skipping."); skipped_count +=1; continue

            insert_response = supabase_client.insert_item(**item_data)
            if insert_response:
                # logger.debug(f"Successfully inserted CISA KEV item for '{cve_id}'.")
                inserted_count += 1
            else:
                logger.error(f"Failed to insert CISA KEV item for '{cve_id}'.")

        except Exception as e:
            logger.error(f"Error processing CISA KEV entry '{kev_entry.get('cveID', 'Unknown CVE')}': {e}", exc_info=True)
            skipped_count +=1

    logger.info(f"Finished processing CISA KEVs. Total entries: {processed_count}. Inserted: {inserted_count}. Skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("CISA KEV JSON Feed Scraper Started")

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set for Supabase client.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_cisa_kev_vulnerabilities()

    logger.info("CISA KEV JSON Feed Scraper Finished")
