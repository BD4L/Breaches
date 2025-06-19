import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
from dateutil import parser as dateutil_parser
import re
import time

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
BREACHSENSE_BASE_URL = "https://www.breachsense.com/breaches/"
SOURCE_ID_BREACHSENSE = 19

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

# Configuration
FILTER_FROM_DATE = os.environ.get("BREACHSENSE_FILTER_FROM_DATE", "2025-06-01")  # Default to beginning of current month
PROCESSING_MODE = os.environ.get("BREACHSENSE_PROCESSING_MODE", "ENHANCED")  # BASIC, ENHANCED, FULL
MAX_BREACHES = int(os.environ.get("BREACHSENSE_MAX_BREACHES", "50"))  # Limit for GitHub Actions

def parse_date_flexible_bs(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', 'ongoing', 'see letter', '']:
        return None
    try:
        # Handle BreachSense date formats like "May 30, 2025" or "Jan 31, 2025"
        dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def parse_leak_size(leak_size_str: str) -> dict:
    """
    Parse leak size string. BreachSense provides data sizes (GB/TB), not individual counts.
    Returns dict with original string only - no estimation of individuals.
    """
    if not leak_size_str or leak_size_str.strip().lower() in ['unknown', 'n/a', '']:
        return {"original": leak_size_str, "size_category": None}

    leak_size_lower = leak_size_str.lower().strip()
    size_category = "unknown"

    try:
        # Categorize leak size for tagging purposes only
        if 'tb' in leak_size_lower:
            size_category = "very_large"  # Terabytes
        elif 'gb' in leak_size_lower:
            gb_match = re.search(r'(\d+(?:\.\d+)?)\s*gb', leak_size_lower)
            if gb_match:
                gb_size = float(gb_match.group(1))
                if gb_size >= 100:
                    size_category = "large"
                elif gb_size >= 10:
                    size_category = "medium"
                else:
                    size_category = "small"
        elif 'mb' in leak_size_lower:
            size_category = "small"  # Megabytes
    except (ValueError, AttributeError) as e:
        logger.debug(f"Could not categorize leak size '{leak_size_str}': {e}")

    return {"original": leak_size_str, "size_category": size_category}

def generate_monthly_url(year: int = None, month: int = None) -> str:
    """
    Generate BreachSense monthly archive URL.
    Defaults to current year and month if not specified.
    """
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    month_names = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december"
    ]

    month_name = month_names[month - 1]
    return f"{BREACHSENSE_BASE_URL}{year}/{month_name}/"

def extract_breach_cards(soup: BeautifulSoup, base_url: str) -> list:
    """
    Extract breach cards from the main BreachSense page.
    Returns list of dicts with basic breach info and detail URLs.
    """
    breach_cards = []

    # Look for breach entries - they appear to be in a specific structure
    # Based on the Firecrawl analysis, breaches are in card format with links
    breach_links = soup.find_all('a', href=True)

    for link in breach_links:
        href = link.get('href', '')
        # Filter for breach detail pages
        if '/breaches/' in href and href != '/breaches/' and not href.endswith('/breaches/'):
            # Skip monthly archive links
            if re.match(r'/breaches/\d{4}/(january|february|march|april|may|june|july|august|september|october|november|december)$', href):
                continue

            # Extract title from the link text or nearby elements
            title = link.get_text(strip=True)
            if not title:
                # Try to find title in nearby h3 or h2 elements
                parent = link.parent
                if parent:
                    title_elem = parent.find(['h3', 'h2', 'h1'])
                    if title_elem:
                        title = title_elem.get_text(strip=True)

            if title and len(title) > 2:  # Basic validation
                full_url = urljoin(base_url, href)
                breach_cards.append({
                    'title': title,
                    'detail_url': full_url,
                    'href': href
                })

    # Remove duplicates based on detail_url
    seen_urls = set()
    unique_cards = []
    for card in breach_cards:
        if card['detail_url'] not in seen_urls:
            seen_urls.add(card['detail_url'])
            unique_cards.append(card)

    return unique_cards

def scrape_breach_detail_page(detail_url: str) -> dict:
    """
    Scrape detailed information from a BreachSense breach detail page.
    Returns dict with comprehensive breach data.
    """
    try:
        time.sleep(1)  # Rate limiting
        response = requests.get(detail_url, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Initialize data structure
        detail_data = {
            'victim': None,
            'threat_actor': None,
            'date_discovered': None,
            'description': None,
            'leak_size': None
        }

        # Look for the data table with breach information
        # Based on Firecrawl analysis, data is in a table format
        tables = soup.find_all('table')

        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)

                    if 'victim' in key:
                        detail_data['victim'] = value
                    elif 'threat actor' in key:
                        detail_data['threat_actor'] = value
                    elif 'date discovered' in key:
                        detail_data['date_discovered'] = value
                    elif 'description' in key:
                        detail_data['description'] = value
                    elif 'leak size' in key:
                        detail_data['leak_size'] = value

        # If table parsing didn't work, try alternative parsing
        if not any(detail_data.values()):
            # Try to extract from page title or headers
            title_elem = soup.find('h1')
            if title_elem:
                title_text = title_elem.get_text(strip=True)
                if 'Data Breach' in title_text:
                    # Extract organization name from title
                    org_match = re.search(r'^(.+?)\s+Data Breach', title_text)
                    if org_match:
                        detail_data['victim'] = org_match.group(1).strip()

        return detail_data

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching breach detail page {detail_url}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error parsing breach detail page {detail_url}: {e}")
        return {}

def should_process_breach(date_discovered: str) -> bool:
    """
    Check if breach should be processed based on date filtering.
    Processes breaches from today forward (today and future dates).
    """
    if not date_discovered or not FILTER_FROM_DATE:
        return True

    try:
        filter_date = datetime.strptime(FILTER_FROM_DATE, "%Y-%m-%d")
        breach_date = dateutil_parser.parse(date_discovered)
        # Include breaches from filter date forward (>= means today and future)
        return breach_date.date() >= filter_date.date()
    except (ValueError, TypeError):
        # If date parsing fails, include the breach
        return True

def process_breachsense_breaches():
    """
    Fetches BreachSense breach listings from monthly archives, processes each notification,
    and inserts relevant data into Supabase using the new monthly URL approach.
    """
    logger.info("Starting BreachSense Breach Notification processing...")
    logger.info(f"Configuration: Filter from {FILTER_FROM_DATE}, Mode: {PROCESSING_MODE}, Max breaches: {MAX_BREACHES}")

    # Generate monthly URL for current month
    monthly_url = generate_monthly_url()
    logger.info(f"Using monthly archive URL: {monthly_url}")

    try:
        response = requests.get(monthly_url, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
        logger.info(f"Successfully fetched BreachSense monthly page. Content length: {len(response.text)} bytes.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching BreachSense monthly page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Extract breach cards from the monthly archive page
    breach_cards = extract_breach_cards(soup, monthly_url)

    if not breach_cards:
        logger.warning("No breach cards found on the monthly archive page. Website structure may have changed.")
        return

    logger.info(f"Found {len(breach_cards)} breach cards on the monthly archive page.")

    # Limit the number of breaches to process (for GitHub Actions)
    if len(breach_cards) > MAX_BREACHES:
        logger.info(f"Limiting processing to {MAX_BREACHES} most recent breaches.")
        breach_cards = breach_cards[:MAX_BREACHES]

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    inserted_count = 0
    processed_count = 0
    skipped_count = 0

    # Process each breach card
    for card_idx, card in enumerate(breach_cards):
        processed_count += 1

        try:
            # Get basic info from card
            org_name = card.get('title', '').strip()
            detail_url = card.get('detail_url', '')

            if not org_name or not detail_url:
                logger.warning(f"Skipping card {card_idx+1} due to missing title or URL.")
                skipped_count += 1
                continue

            # Check if item already exists in database
            if supabase_client.check_item_exists(detail_url):
                logger.info(f"Breach '{org_name}' already exists in database. Skipping.")
                skipped_count += 1
                continue

            # Scrape detailed information from the breach detail page
            if PROCESSING_MODE in ['ENHANCED', 'FULL']:
                logger.info(f"Fetching detailed info for '{org_name}' from {detail_url}")
                detail_data = scrape_breach_detail_page(detail_url)
            else:
                detail_data = {}

            # Use detailed data if available, otherwise use card data
            victim_name = detail_data.get('victim', org_name)
            threat_actor = detail_data.get('threat_actor', '')
            date_discovered = detail_data.get('date_discovered', '')
            description = detail_data.get('description', '')
            leak_size = detail_data.get('leak_size', '')

            # Apply date filtering
            if date_discovered and not should_process_breach(date_discovered):
                logger.info(f"Skipping '{victim_name}' - breach date {date_discovered} is before filter date {FILTER_FROM_DATE}")
                skipped_count += 1
                continue

            # Parse dates
            publication_date_iso = parse_date_flexible_bs(date_discovered) if date_discovered else None
            breach_date_text = date_discovered if date_discovered else None

            # Parse leak size for categorization only (no individual count estimation)
            leak_size_data = parse_leak_size(leak_size) if leak_size else {"original": None, "size_category": None}

            # Generate comprehensive summary
            summary = f"Data breach at {victim_name}."
            if threat_actor:
                summary += f" Threat actor: {threat_actor}."
            if description:
                summary += f" {description}"
            if leak_size:
                summary += f" Leak size: {leak_size}."

            # Build raw data for storage
            raw_data = {
                "original_date_string": date_discovered,
                "threat_actor": threat_actor,
                "leak_size_original": leak_size,
                "leak_size_category": leak_size_data.get("size_category"),
                "description": description,
                "detail_page_url": detail_url
            }
            raw_data_json = {k: v for k, v in raw_data.items() if v is not None and str(v).strip().lower() not in ['n/a', 'unknown', '', 'pending', 'not specified']}

            # Generate tags
            tags = ["breachsense", "data_breach", "ransomware"]
            if threat_actor:
                # Add threat actor as tag
                threat_actor_tag = threat_actor.lower().replace(" ", "_").replace("-", "_")
                tags.append(threat_actor_tag)

            # Add tag based on data size category (not individual count)
            size_category = leak_size_data.get("size_category")
            if size_category:
                if size_category == "very_large":
                    tags.append("very_large_data_leak")
                elif size_category == "large":
                    tags.append("large_data_leak")
                elif size_category == "medium":
                    tags.append("medium_data_leak")
                elif size_category == "small":
                    tags.append("small_data_leak")

            # Prepare data for database insertion (no affected_individuals field)
            item_data = {
                "source_id": SOURCE_ID_BREACHSENSE,
                "item_url": detail_url,
                "title": victim_name,
                "publication_date": publication_date_iso,
                "summary_text": summary.strip(),
                "raw_data_json": raw_data_json,
                "tags_keywords": list(set(tags)),
                "breach_date": breach_date_text,
                "what_was_leaked": description if description else None
            }

            # Insert into database
            insert_response = supabase_client.insert_item(**item_data)
            if insert_response:
                logger.info(f"Successfully inserted breach for '{victim_name}'. URL: {detail_url}")
                inserted_count += 1
            else:
                logger.error(f"Failed to insert breach for '{victim_name}'.")
                skipped_count += 1

        except Exception as e:
            logger.error(f"Error processing breach card for '{org_name if 'org_name' in locals() else 'Unknown Entity'}': {e}", exc_info=True)
            skipped_count += 1

    logger.info(f"Finished processing BreachSense breaches. Total items processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

    if inserted_count == 0 and processed_count > 0:
        logger.warning("No breaches were inserted. This might indicate a parsing issue or all breaches were already in the database.")
    elif inserted_count > 0:
        logger.info(f"Successfully processed {inserted_count} new breaches from BreachSense.")

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
