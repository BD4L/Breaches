import os
import logging
import requests
import csv
import io
import hashlib
from datetime import datetime, date
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
CALIFORNIA_AG_BREACH_URL = "https://oag.ca.gov/privacy/databreach/list"
CALIFORNIA_AG_CSV_URL = "https://oag.ca.gov/privacy/databreach/list-export"
SOURCE_ID_CALIFORNIA_AG = 4 # California AG source ID

# Configuration for date filtering
# Set to None to collect all historical data (for testing)
# Set to a date string like "2025-05-27" for production filtering
FILTER_FROM_DATE = os.environ.get("CA_AG_FILTER_FROM_DATE", None)  # None = collect all data

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://oag.ca.gov/' # Referer can sometimes help
}

def generate_incident_uid(organization_name: str, reported_date: str) -> str:
    """
    Generate a unique incident identifier for deduplication.
    """
    # Create a unique string combining organization and reported date
    unique_string = f"ca_ag_{organization_name}_{reported_date}".lower().replace(" ", "_")
    # Generate a hash for consistent UIDs
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

def parse_date_flexible(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO format date string or None if parsing fails.
    """
    if not date_str or date_str.strip() == "" or date_str.strip().lower() == "n/a":
        return None

    try:
        # Clean up the date string
        date_str = date_str.strip()

        # Handle multiple dates (take the first one)
        if ',' in date_str:
            date_str = date_str.split(',')[0].strip()

        # Handle common formats
        parsed_date = dateutil_parser.parse(date_str)
        return parsed_date.strftime('%Y-%m-%d')
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse date '{date_str}': {e}")
        return None

def parse_breach_dates(date_str: str) -> list:
    """
    Parse multiple breach dates from a comma-separated string.
    """
    if not date_str or date_str.strip() == "" or date_str.strip().lower() == "n/a":
        return []

    dates = []
    for date_part in date_str.split(','):
        parsed_date = parse_date_flexible(date_part.strip())
        if parsed_date:
            dates.append(parsed_date)

    return dates

def fetch_csv_data() -> list:
    """
    Fetch breach data from the CSV endpoint (Tier 1 - Portal Raw Data).
    """
    logger.info("Fetching California AG breach data from CSV endpoint...")

    try:
        response = requests.get(CALIFORNIA_AG_CSV_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()

        # Parse CSV data
        csv_data = []
        csv_reader = csv.DictReader(io.StringIO(response.text))

        for row in csv_reader:
            # Generate incident UID for deduplication
            incident_uid = generate_incident_uid(
                row.get('Organization Name', ''),
                row.get('Reported Date', '')
            )

            # Parse dates
            breach_dates = parse_breach_dates(row.get('Date(s) of Breach (if known)', ''))
            reported_date = parse_date_flexible(row.get('Reported Date', ''))

            # Create standardized breach record
            breach_record = {
                'organization_name': row.get('Organization Name', '').strip(),
                'breach_dates': breach_dates,
                'reported_date': reported_date,
                'incident_uid': incident_uid,
                'detail_url': f"https://oag.ca.gov/ecrime/databreach/reports/{incident_uid}" if incident_uid else None,
                'raw_csv_data': dict(row)
            }

            csv_data.append(breach_record)

        logger.info(f"Successfully parsed {len(csv_data)} breach records from CSV")
        return csv_data

    except Exception as e:
        logger.error(f"Failed to fetch CSV data: {e}")
        return []

def enhance_breach_data(breach_record: dict) -> dict:
    """
    Enhance breach data by fetching detailed information (Tier 2 - Derived/Enriched).
    """
    try:
        # Look for potential detail page URLs in the main listing
        # This would require additional scraping of the main page to find actual URLs
        # For now, we'll use the data we have and mark for future enhancement

        enhanced_data = breach_record.copy()
        enhanced_data['enhancement_attempted'] = True
        enhanced_data['enhancement_timestamp'] = datetime.now().isoformat()

        return enhanced_data

    except Exception as e:
        logger.error(f"Failed to enhance breach data for {breach_record.get('organization_name', 'Unknown')}: {e}")
        return breach_record

def process_california_ag_breaches():
    """
    Enhanced California AG breach scraper using 3-tier approach.
    """
    logger.info("Starting enhanced California AG breach data fetch...")

    try:
        # Initialize Supabase client
        supabase_client = SupabaseClient()

        # Tier 1: Fetch raw CSV data
        csv_breach_data = fetch_csv_data()
        if not csv_breach_data:
            logger.error("No CSV data retrieved, aborting")
            return

        # Filter breaches based on configuration
        if FILTER_FROM_DATE:
            # Production mode: filter from specified date
            try:
                filter_date = datetime.strptime(FILTER_FROM_DATE, '%Y-%m-%d').date()
                logger.info(f"Production mode: filtering breaches from {filter_date} onward")
            except ValueError:
                logger.warning(f"Invalid FILTER_FROM_DATE format '{FILTER_FROM_DATE}', using today's date")
                filter_date = date.today()
        else:
            # Testing mode: collect all historical data
            filter_date = None
            logger.info("Testing mode: collecting ALL historical breach data (no date filtering)")

        filtered_breaches = []

        for breach in csv_breach_data:
            if filter_date is None:
                # No filtering - include all breaches
                filtered_breaches.append(breach)
            elif breach['reported_date']:
                try:
                    # Parse the YYYY-MM-DD format from our parse_date_flexible function
                    reported_date_obj = datetime.strptime(breach['reported_date'], '%Y-%m-%d').date()
                    if reported_date_obj >= filter_date:
                        filtered_breaches.append(breach)
                except ValueError:
                    # If date parsing fails, include the breach to be safe
                    filtered_breaches.append(breach)
            else:
                # If no reported date, include the breach
                filtered_breaches.append(breach)

        if filter_date:
            logger.info(f"Filtered to {len(filtered_breaches)} breaches (from {filter_date} onward)")
        else:
            logger.info(f"Collected {len(filtered_breaches)} total historical breaches (no filtering)")

        # Process each breach record
        processed_count = 0
        for breach_record in filtered_breaches:
            try:
                # Tier 2: Enhance with additional data
                enhanced_record = enhance_breach_data(breach_record)

                # Convert to database format
                db_item = {
                    'source_id': SOURCE_ID_CALIFORNIA_AG,
                    'item_url': enhanced_record.get('detail_url', CALIFORNIA_AG_BREACH_URL),
                    'title': enhanced_record['organization_name'],
                    'publication_date': enhanced_record['reported_date'],
                    'summary_text': f"Data breach reported by {enhanced_record['organization_name']}",
                    'full_content': f"Organization: {enhanced_record['organization_name']}\n"
                                  f"Breach Date(s): {', '.join(enhanced_record['breach_dates']) if enhanced_record['breach_dates'] else 'Not specified'}\n"
                                  f"Reported Date: {enhanced_record['reported_date'] or 'Not specified'}",
                    'reported_date': enhanced_record['reported_date'],
                    'breach_date': enhanced_record['breach_dates'][0] if enhanced_record['breach_dates'] else None,
                    'raw_data_json': {
                        'scraper_version': '2.0_enhanced',
                        'tier_1_csv_data': enhanced_record['raw_csv_data'],
                        'tier_2_enhanced': {
                            'incident_uid': enhanced_record['incident_uid'],
                            'breach_dates_all': enhanced_record['breach_dates'],
                            'enhancement_attempted': enhanced_record.get('enhancement_attempted', False),
                            'enhancement_timestamp': enhanced_record.get('enhancement_timestamp')
                        }
                    }
                }

                # Insert into database
                supabase_client.insert_scraped_item(db_item)
                processed_count += 1
                logger.info(f"Processed: {enhanced_record['organization_name']}")

            except Exception as e:
                logger.error(f"Failed to process breach record for {breach_record.get('organization_name', 'Unknown')}: {e}")

        logger.info(f"California AG enhanced breach fetch completed. Processed {processed_count} items.")

    except Exception as e:
        logger.error(f"Unexpected error in California AG breach fetch: {e}")

# Legacy function name for compatibility
def fetch_california_ag_breaches():
    """
    Legacy function name - calls the enhanced process function.
    """
    return process_california_ag_breaches()

if __name__ == "__main__":
    logger.info("California AG Security Breach Scraper Started")

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_california_ag_breaches()

    logger.info("California AG Security Breach Scraper Finished")
