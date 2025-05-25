import os
import logging
import requests
import time
from datetime import datetime, timedelta, timezone
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
NVD_API_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
SOURCE_ID_NVD_API = 38
NVD_DETAIL_URL_BASE = "https://nvd.nist.gov/vuln/detail/"
USER_AGENT = "PwnedBreachScraper/1.0 (github.com/ComprehensiveBreachDataDashboard/Breaches)" # Example User-Agent

# Rate Limiting:
# Without API key: 5 requests in a rolling 30-second window (avg 1 request every 6 seconds)
# With API key: 50 requests in a rolling 30-second window (avg 1 request every 0.6 seconds)
# We'll use slightly more conservative delays.
DELAY_NO_KEY_SECONDS = 7.0
DELAY_WITH_KEY_SECONDS = 1.0 # Increased from 0.6 for safety
RESULTS_PER_PAGE = 2000 # Max allowed by NVD API is 2000

def parse_date_nvd(date_str: str) -> str | None:
    """
    Parses date string (typically ISO with Z or offset) from NVD to ISO 8601 format.
    """
    if not date_str:
        return None
    try:
        dt_object = dateutil_parser.isoparse(date_str)
        return dt_object.isoformat()
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not parse date string from NVD: '{date_str}'. Error: {e}")
        return None

def get_english_description(descriptions: list) -> str:
    """Extracts the English description from the list of descriptions."""
    for desc in descriptions:
        if desc.get("lang") == "en":
            return desc.get("value", "No English description available.")
    return "No English description available."

def get_cvss_v31_info(metrics: dict) -> tuple[float | None, str | None]:
    """Extracts CVSS v3.1 score and severity."""
    if "cvssMetricV31" in metrics:
        for metric_v31 in metrics["cvssMetricV31"]: # It's a list
            cvss_data = metric_v31.get("cvssData")
            if cvss_data:
                score = cvss_data.get("baseScore")
                severity = cvss_data.get("baseSeverity") # e.g. CRITICAL, HIGH, MEDIUM, LOW
                return score, severity
    return None, None

def get_cwe_ids(weaknesses: list) -> list[str]:
    """Extracts CWE IDs from the weaknesses list."""
    cwe_ids = []
    if weaknesses:
        for weakness in weaknesses:
            # Each weakness can have multiple descriptions, pick 'en' one with CWE ID
            for desc in weakness.get("description", []):
                if desc.get("lang") == "en" and desc.get("value", "").startswith("CWE-"):
                    cwe_ids.append(desc["value"])
    return list(set(cwe_ids)) # Unique CWEs


def process_nvd_cve_api():
    """
    Fetches CVE data from the NVD API for recently modified CVEs
    and inserts them into Supabase.
    """
    logger.info("Starting NVD CVE API processing...")

    nvd_api_key = os.environ.get("NVD_API_KEY")
    api_delay = DELAY_NO_KEY_SECONDS
    headers = {'User-Agent': USER_AGENT}

    if nvd_api_key:
        logger.info("NVD_API_KEY found. Using API key for requests.")
        headers['apiKey'] = nvd_api_key # NVD docs specify 'apiKey' as a header
        api_delay = DELAY_WITH_KEY_SECONDS
    else:
        logger.info("NVD_API_KEY not found. Making requests without an API key (slower rate).")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    # Define date range for query (e.g., last 7 days)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=7)
    
    # NVD API format: YYYY-MM-DDTHH:mm:ss.SSSZ (example from docs for resultsPerPage > 2000)
    # For query params, YYYY-MM-DDTHH:mm:ssZ should also work.
    # Using .isoformat() and replacing +00:00 with Z for consistency.
    last_mod_start_date_str = start_date.isoformat().replace("+00:00", "Z")
    last_mod_end_date_str = end_date.isoformat().replace("+00:00", "Z")

    logger.info(f"Querying NVD API for CVEs modified between {last_mod_start_date_str} and {last_mod_end_date_str}")

    params = {
        'lastModStartDate': last_mod_start_date_str,
        'lastModEndDate': last_mod_end_date_str,
        'resultsPerPage': RESULTS_PER_PAGE,
        'startIndex': 0
    }

    total_inserted_all_pages = 0
    total_processed_all_pages = 0
    total_skipped_all_pages = 0
    
    page_num = 0
    while True:
        params['startIndex'] = page_num * RESULTS_PER_PAGE
        logger.info(f"Requesting page {page_num + 1} (startIndex: {params['startIndex']}) from NVD API...")
        
        # Implement delay before API call
        logger.info(f"Waiting for {api_delay} seconds before API call...")
        time.sleep(api_delay)

        try:
            response = requests.get(NVD_API_BASE_URL, headers=headers, params=params, timeout=60)
            
            if response.status_code == 403 and not nvd_api_key: # Forbidden, often due to rate limit without key
                 logger.error(f"NVD API request failed with status 403 (Forbidden). Likely rate limit without API key. Try again later or add key. Response: {response.text[:500]}")
                 break 
            elif response.status_code == 403 and nvd_api_key: # Forbidden with key
                 logger.error(f"NVD API request failed with status 403 (Forbidden) even with API key. Check key or User-Agent. Response: {response.text[:500]}")
                 break
            
            response.raise_for_status() # Raise an exception for other bad status codes
            
            api_response = response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data from NVD API (page {page_num + 1}): {e}", exc_info=True)
            break # Stop on error
        except ValueError as e_json: # Includes JSONDecodeError
            logger.error(f"Error decoding JSON response from NVD API (page {page_num + 1}): {e_json}. Response text: {response.text[:500]}")
            break

        vulnerabilities = api_response.get("vulnerabilities", [])
        if not vulnerabilities:
            logger.info(f"No more vulnerabilities found on page {page_num + 1} or end of results.")
            break

        logger.info(f"Fetched {len(vulnerabilities)} CVE entries on page {page_num + 1}.")
        
        page_inserted_count = 0
        page_processed_count = 0
        page_skipped_count = 0

        for cve_item_wrapper in vulnerabilities:
            cve = cve_item_wrapper.get("cve")
            if not cve:
                logger.warning(f"Skipping item due to missing 'cve' object. Item: {cve_item_wrapper}")
                page_skipped_count += 1
                continue
            
            page_processed_count += 1
            try:
                cve_id = cve.get("id")
                if not cve_id:
                    logger.warning(f"Skipping CVE item due to missing 'id'. Item: {cve}")
                    page_skipped_count += 1
                    continue

                item_url = urljoin(NVD_DETAIL_URL_BASE, cve_id)
                
                english_description = get_english_description(cve.get("descriptions", []))
                first_sentence_description = english_description.split('.')[0] + '.' if '.' in english_description else english_description
                
                title = f"NVD: {cve_id} - {first_sentence_description}"
                if len(title) > 250: title = title[:247] + "..." # Truncate if too long

                publication_date_iso = parse_date_nvd(cve.get("published"))
                if not publication_date_iso:
                    logger.warning(f"Skipping CVE '{cve_id}' due to unparsable published date: '{cve.get('published')}'.")
                    page_skipped_count +=1
                    continue
                
                last_modified_iso = parse_date_nvd(cve.get("lastModified"))
                vuln_status = cve.get("vulnStatus")
                source_identifier = cve.get("sourceIdentifier")
                
                cvss_v31_score, cvss_v31_severity = get_cvss_v31_info(cve.get("metrics", {}))
                cwe_ids = get_cwe_ids(cve.get("weaknesses", []))
                
                # Basic extraction for references, configurations (can be complex)
                references_list = [ref.get("url") for ref in cve.get("references", []) if ref.get("url")]
                # Configurations can be very detailed; for now, just indicate if present or basic info.
                # Storing full configurations can make raw_data_json very large.
                # Example: list of affected products/versions if simple.
                configurations_summary = "Configuration details present in NVD record." if cve.get("configurations") else "No specific configurations listed."


                raw_data = {
                    "cve_id": cve_id,
                    "last_modified": last_modified_iso,
                    "vuln_status": vuln_status,
                    "source_identifier": source_identifier,
                    "cvss_v31_score": cvss_v31_score,
                    "cvss_v31_severity": cvss_v31_severity,
                    "cwe_ids": cwe_ids if cwe_ids else None, # Store as list or null
                    "references_list": references_list if references_list else None,
                    "configurations_summary": configurations_summary, # Or more detailed if needed
                    # Full metrics, weaknesses, configurations can be stored if required, but are verbose
                    # "metrics_full": cve.get("metrics"), 
                    # "weaknesses_full": cve.get("weaknesses"),
                }
                raw_data_json = {k: v for k, v in raw_data.items() if v is not None}

                tags = ["nvd", "cve", cve_id]
                if cvss_v31_severity: tags.append(cvss_v31_severity.lower())
                if cwe_ids: tags.extend(cwe_ids) # CWEs are already formatted like CWE-XXX
                
                tags = list(set(tags))

                item_data = {
                    "source_id": SOURCE_ID_NVD_API,
                    "item_url": item_url,
                    "title": title,
                    "publication_date": publication_date_iso,
                    "summary_text": english_description,
                    "raw_data_json": raw_data_json,
                    "tags_keywords": tags
                }
                
                # TODO: Implement check for existing record (e.g., by cve_id in raw_data_json and source_id)
                # query_result = supabase_client.client.table("scraped_items").select("id").eq("raw_data_json->>cve_id", cve_id).eq("source_id", SOURCE_ID_NVD_API).execute()
                # if query_result.data: logger.info(f"NVD item for '{cve_id}' already exists. Skipping."); page_skipped_count +=1; continue


                insert_response = supabase_client.insert_item(**item_data)
                if insert_response:
                    page_inserted_count += 1
                else:
                    logger.error(f"Failed to insert NVD item for '{cve_id}'.")

            except Exception as e:
                logger.error(f"Error processing NVD CVE item '{cve.get('id', 'Unknown ID')}': {e}", exc_info=True)
                page_skipped_count +=1
        
        logger.info(f"Page {page_num + 1} processing summary - Processed: {page_processed_count}, Inserted: {page_inserted_count}, Skipped: {page_skipped_count}")
        total_inserted_all_pages += page_inserted_count
        total_processed_all_pages += page_processed_count
        total_skipped_all_pages += page_skipped_count
        
        # Check if this was the last page
        total_results = api_response.get("totalResults", 0)
        if (params['startIndex'] + len(vulnerabilities)) >= total_results:
            logger.info("All available results processed.")
            break
        
        page_num += 1 # Increment for next page

    logger.info(f"Finished processing NVD CVE API. Total CVEs processed: {total_processed_all_pages}. Total inserted: {total_inserted_all_pages}. Total skipped: {total_skipped_all_pages}")

if __name__ == "__main__":
    logger.info("NVD CVE API Scraper Started")
    
    if not os.environ.get("NVD_API_KEY"):
        print("-----------------------------------------------------------------------------------")
        print("INFO: NVD_API_KEY environment variable is not set.")
        print("The script will run at a slower rate. For faster processing, obtain an API key")
        print("from NVD (https://nvd.nist.gov/developers/request-an-api-key) and set it.")
        print("-----------------------------------------------------------------------------------")

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set for Supabase client.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_nvd_cve_api()
        
    logger.info("NVD CVE API Scraper Finished")
