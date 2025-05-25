import os
import logging
import time
import json # For pretty printing raw_data_json if needed, or if actor output is complex JSON strings
from datetime import datetime
from dateutil import parser as dateutil_parser
from apify_client import ApifyClient

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
SOURCE_ID_TEXAS_APIFY = 39

def parse_date_apify_result(date_str: str) -> str | None:
    """
    Tries to parse a date string from Apify actor result using dateutil.parser.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or str(date_str).strip().lower() in ['n/a', 'unknown', 'pending', 'various', '']:
        return None
    try:
        # dateutil.parser is very flexible with input formats
        dt_object = dateutil_parser.parse(str(date_str)) # Ensure input is string
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string from Apify result: '{date_str}'. Error: {e}")
        return None

def process_texas_apify_breaches():
    """
    Runs an Apify actor for Texas breach data, fetches the results,
    and inserts them into Supabase.
    """
    logger.info("Starting Texas Breach Data processing via Apify...")

    apify_api_token = os.environ.get("APIFY_API_TOKEN")
    apify_actor_id = os.environ.get("APIFY_TEXAS_BREACH_ACTOR_ID")

    if not apify_api_token:
        logger.error("CRITICAL: APIFY_API_TOKEN environment variable not found. This script cannot run without it.")
        return
    if not apify_actor_id:
        logger.error("CRITICAL: APIFY_TEXAS_BREACH_ACTOR_ID environment variable not found. This script cannot run without it.")
        logger.error("This should be the ID of your Apify actor (e.g., 'your-username/my-texas-breach-actor').")
        return

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    try:
        logger.info(f"Initializing ApifyClient with token...")
        apify_client = ApifyClient(apify_api_token)
        
        logger.info(f"Getting Apify actor: {apify_actor_id}")
        actor = apify_client.actor(apify_actor_id)
        
        logger.info(f"Starting Apify actor run for {apify_actor_id}... (This may take some time)")
        # If your actor requires specific input, provide it in `run_input`.
        # For example: actor_input = {"some_param": "value"}
        # run = actor.call(run_input=actor_input)
        run = actor.call() # Assuming default input is sufficient
        
        logger.info(f"Apify actor run started. Run ID: {run.get('id')}, Dataset ID: {run.get('defaultDatasetId')}")
        logger.info("Waiting for actor run to finish and retrieve dataset items...")
        
        # Fetch items from the dataset associated with the run
        # The .list_items() method handles pagination automatically.
        # iterate_items() is a generator, convert to list to get all items if memory allows,
        # or process item by item if dataset is very large.
        dataset = apify_client.dataset(run["defaultDatasetId"])
        # Using iterate_items() and processing one by one might be more memory efficient for large datasets.
        # However, list() is simpler if dataset size is manageable.
        dataset_items = list(dataset.iterate_items())

        if not dataset_items:
            logger.info(f"No items found in the dataset for run ID {run.get('id')}.")
            return
            
        logger.info(f"Successfully fetched {len(dataset_items)} items from Apify actor run.")

    except Exception as e_apify:
        logger.error(f"An error occurred while running Apify actor or fetching results: {e_apify}", exc_info=True)
        return

    inserted_count = 0
    processed_count = 0
    skipped_count = 0

    # --- IMPORTANT ASSUMPTION ---
    # The structure of `item` below depends ENTIRELY on the output of YOUR Apify actor.
    # You MUST adjust the field names (e.g., item.get("entityName"), item.get("dateOfBreach"))
    # to match the actual keys in the JSON objects your actor produces.
    logger.warning("Processing Apify results: Field names used for 'entityName', 'breachDate', 'reportDate', 'affectedCount', 'breachType', 'noticeUrl', 'summary' are EXAMPLES. You MUST verify and adjust them based on your Apify actor's output structure.")

    for item_idx, item in enumerate(dataset_items):
        processed_count += 1
        try:
            # --- ADJUST THESE FIELD NAMES BASED ON YOUR APIFY ACTOR'S OUTPUT ---
            entity_name = item.get("entityName") or item.get("organizationName") or item.get("companyName")
            
            # Try multiple date fields, prioritize specific ones
            date_reported_str = item.get("dateReported") or item.get("notificationDate") or item.get("dateSubmitted")
            date_of_breach_str = item.get("dateOfBreach") or item.get("breachDate") 
            
            # If only one date is available in item, use it for publication_date
            # and potentially as breach date if no other is specified.
            if not date_reported_str and date_of_breach_str:
                date_reported_str = date_of_breach_str # Use breach date as report date if report date missing
            elif not date_of_breach_str and date_reported_str: # Less common, but if only report date
                 pass # We'll use date_reported_str for publication, breach date will be unknown

            # If no specific date fields, look for a generic 'date' field
            if not date_reported_str and not date_of_breach_str:
                date_reported_str = item.get("date") # Generic fallback

            affected_count_str = str(item.get("affectedCount") or item.get("individualsAffected") or item.get("recordsAffected", "Not specified"))
            breach_type = item.get("breachType") or item.get("typeOfBreach", "Not specified")
            notice_url = item.get("noticeUrl") or item.get("sourceUrl") or item.get("url")
            summary_detail = item.get("summary") or item.get("description")
            # --- END OF ADJUSTABLE FIELD NAMES ---

            if not entity_name:
                logger.warning(f"Skipping item #{item_idx+1} from Apify due to missing entity name. Item: {json.dumps(item, indent=2)[:300]}")
                skipped_count += 1
                continue

            publication_date_iso = parse_date_apify_result(date_reported_str)
            if not publication_date_iso:
                # If primary (reported) date fails, try breach date for publication
                publication_date_iso = parse_date_apify_result(date_of_breach_str)
                if not publication_date_iso:
                    logger.warning(f"Skipping item for '{entity_name}' due to unparsable/missing primary date (Reported: '{date_reported_str}', Breach: '{date_of_breach_str}'). Item: {json.dumps(item, indent=2)[:300]}")
                    skipped_count +=1
                    continue
                else:
                    logger.info(f"Used breach date ('{date_of_breach_str}') as publication date for '{entity_name}' as reported date was missing/unparsable.")
            
            item_url_to_store = notice_url if notice_url else f"texas_apify_breach_{entity_name.replace(' ','_')}_{publication_date_iso}"

            summary_text = f"Breach at {entity_name}."
            if breach_type and breach_type.lower() != 'not specified':
                summary_text += f" Type: {breach_type}."
            if date_of_breach_str and date_of_breach_str != date_reported_str : # Add if different from pub date
                 parsed_breach_date = parse_date_apify_result(date_of_breach_str)
                 if parsed_breach_date: summary_text += f" Approx. Breach Date: {parsed_breach_date.split('T')[0]}."
            if affected_count_str.isdigit() and int(affected_count_str) > 0:
                summary_text += f" Individuals Affected: {affected_count_str}."
            if summary_detail and len(summary_detail) > 10: # Add provided summary if substantial
                summary_text += f" Details: {summary_detail[:300]}{'...' if len(summary_detail) > 300 else ''}"
            

            raw_data_json_payload = item # Store the whole Apify item

            tags = ["texas_ag", "tx_breach", "apify"]
            if breach_type and breach_type.lower() != 'not specified':
                tags.append(breach_type.lower().replace(" ", "_").replace("/", "_"))
            
            # Add tag for scale if affected_count is numeric
            if affected_count_str.isdigit():
                num_affected = int(affected_count_str)
                if num_affected >= 1000000: tags.append("large_scale_breach")
                elif num_affected >= 100000: tags.append("medium_scale_breach")

            item_data = {
                "source_id": SOURCE_ID_TEXAS_APIFY,
                "item_url": item_url_to_store,
                "title": entity_name,
                "publication_date": publication_date_iso,
                "summary_text": summary_text.strip(),
                "raw_data_json": raw_data_json_payload,
                "tags_keywords": list(set(tags))
            }
            
            # TODO: Implement check for existing record before inserting (e.g., by a unique ID from Apify if available, or combination of fields)

            insert_response = supabase_client.insert_item(**item_data)
            if insert_response:
                # logger.debug(f"Successfully inserted Apify item for '{entity_name}'.")
                inserted_count += 1
            else:
                logger.error(f"Failed to insert Apify item for '{entity_name}'.")

        except Exception as e_item:
            logger.error(f"Error processing Apify item #{item_idx+1}: {json.dumps(item, indent=2)[:300]}. Error: {e_item}", exc_info=True)
            skipped_count +=1

    logger.info(f"Finished processing Texas AG Apify results. Total items from actor: {processed_count}. Inserted: {inserted_count}. Skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("Texas AG (via Apify) Scraper Started")
    
    if not os.environ.get("APIFY_API_TOKEN") or not os.environ.get("APIFY_TEXAS_BREACH_ACTOR_ID"):
        print("-----------------------------------------------------------------------------------")
        print("ERROR: Required environment variables APIFY_API_TOKEN or APIFY_TEXAS_BREACH_ACTOR_ID are not set.")
        print("This script requires an Apify API token AND the ID of your Apify actor for Texas breach data.")
        print("Please set these environment variables to proceed.")
        print("  - APIFY_API_TOKEN: Your Apify API token.")
        print("  - APIFY_TEXAS_BREACH_ACTOR_ID: The ID of your actor (e.g., 'your-username/my-texas-actor').")
        print("-----------------------------------------------------------------------------------")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set for Supabase client.")
    # Proceed only if all critical env vars for Apify are set
    elif os.environ.get("APIFY_API_TOKEN") and os.environ.get("APIFY_TEXAS_BREACH_ACTOR_ID"):
        logger.info("Supabase and Apify environment variables seem to be set.")
        process_texas_apify_breaches()
    else:
        logger.info("Script will not run due to missing Apify environment variables as noted above.")
        
    logger.info("Texas AG (via Apify) Scraper Finished")
