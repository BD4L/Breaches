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
VERMONT_AG_BREACH_URL = "http://ago.vermont.gov/data-security-breaches/" # Note: HTTP, might redirect to HTTPS
SOURCE_ID_VERMONT_AG = 17

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_flexible_vt(date_str: str) -> str | None:
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

def process_vermont_ag_breaches():
    """
    Fetches Vermont AG data security breach notifications, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting Vermont AG Data Security Breach processing...")

    final_url_to_scrape = VERMONT_AG_BREACH_URL
    try:
        # Perform a HEAD request first to resolve redirects (e.g. HTTP to HTTPS)
        head_response = requests.head(VERMONT_AG_BREACH_URL, headers=REQUEST_HEADERS, allow_redirects=True, timeout=15)
        head_response.raise_for_status()
        final_url_to_scrape = head_response.url
        logger.info(f"Initial URL '{VERMONT_AG_BREACH_URL}' resolved to '{final_url_to_scrape}'.")
        
        response = requests.get(final_url_to_scrape, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Vermont AG breach data page from {final_url_to_scrape}: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Vermont AG site structure (ago.vermont.gov):
    # Data is typically within a main content area, often <div id="main-content"> or <article>.
    # The page lists breaches by year, often under headers (e.g., <h3>2023 Security Breaches</h3>).
    # Inside each year's section, there's usually a list (<ul>) of links to PDF notices.
    # Each list item <li> contains the link, and the text includes Entity Name, Date Reported, and sometimes # affected.
    
    content_area = soup.find(id="main-content") or soup.find('article') or soup.find('main')
    if not content_area:
        logger.warning("Could not find a specific main content area. Searching the whole page.")
        content_area = soup # Fallback to whole page

    # Find all year headers to iterate through sections
    # Year headers are usually <h3> like "2023 Security Breaches Reported to the Attorney General"
    year_headers = content_area.find_all(['h2', 'h3', 'h4'], string=re.compile(r'\d{4}\s+Security\s+Breaches', re.IGNORECASE))

    if not year_headers:
        logger.warning("No year-based headers found. Attempting to find breach list items directly in the content area.")
        # Fallback: Create a dummy header to process any <ul> found directly in content_area
        class DummyHeader:
            def __init__(self, text, element_source):
                self.text = text
                self.element_source = element_source
            def find_next_sibling(self, name): # Simulate finding <ul> after this "header"
                if name == 'ul': return self.element_source.find('ul')
                return None
        
        # Check if there's a main <ul> that looks like a breach list
        main_ul_list = content_area.find('ul')
        if main_ul_list and main_ul_list.find('li') and main_ul_list.find('li').find('a', href=True):
            logger.info("No year headers, but found a main list. Processing items under 'Uncategorized Year'.")
            year_headers = [DummyHeader("Uncategorized Year Security Breaches", content_area)]
        else:
            logger.error("No year-based headers and no direct list of breach items found. Cannot proceed.")
            # logger.debug(f"Page content sample (first 1000 chars): {response.text[:1000]}")
            return
        
    logger.info(f"Found {len(year_headers)} year sections/groupings to process.")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    total_processed = 0
    total_inserted = 0
    total_skipped = 0
    
    for header in year_headers:
        year_text_full = header.text # e.g., "2023 Security Breaches Reported..."
        year_match = re.search(r'(\d{4})', year_text_full)
        year_for_tag = year_match.group(1) if year_match else "unknown_year"
        logger.info(f"Processing section: '{year_text_full}' (Year: {year_for_tag})")

        # Breaches are usually in a <ul> following the header.
        ul_list = header.find_next_sibling('ul')
        if isinstance(header, DummyHeader): # For fallback case
            ul_list = header.element_source.find('ul') 

        if not ul_list:
            logger.warning(f"No <ul> element found following header for '{year_text_full}'. Skipping this section.")
            continue
            
        notifications = ul_list.find_all('li')
        if not notifications:
            logger.info(f"No breach notification list items (<li>) found in section '{year_text_full}'.")
            continue
        
        logger.info(f"Found {len(notifications)} potential breach notifications in section '{year_text_full}'.")
        
        page_processed_count = 0
        page_inserted_count = 0
        page_skipped_count = 0

        # Structure of <li>:
        # Entity Name (Date Reported to AG) – Approximate # of Vermonters Affected (Link to Notice)
        # Example: "Org ABC (1/1/2023) - Approx. 100 Vermonters Affected (Notice)"
        # Date and Vermonters affected might be missing or in different formats.

        for item_idx, li_item in enumerate(notifications):
            page_processed_count += 1
            try:
                full_text = li_item.get_text(separator=' ', strip=True)
                link_tag = li_item.find('a', href=True) # Link is usually on "Notice" or part of the text
                
                item_specific_url = None
                if link_tag:
                    item_specific_url = urljoin(final_url_to_scrape, link_tag['href'])
                
                # Regex to parse: Entity Name (Date Reported) – Optional Vermonters Affected
                # Example: (.*?)\s*\((\d{1,2}/\d{1,2}/\d{2,4})\)(?:\s*–\s*Approx\.?\s*([\d,]+)\s*Vermonters\s+Affected)?
                # This regex attempts to capture:
                # Group 1: Entity Name
                # Group 2: Date Reported
                # Group 3 (Optional): Number of Vermonters Affected
                
                # Pattern for date: MM/DD/YYYY or Month D, YYYY
                date_pattern = r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"
                
                # Main parsing logic for "Entity Name (Date Reported)"
                # The structure is quite consistent: Entity (Date) - Rest
                main_match = re.match(fr'^(.*?)\s*\(\s*({date_pattern})\s*\)', full_text)
                
                org_name = None
                date_reported_str = None
                residents_affected_str = "Not specified"

                if main_match:
                    org_name = main_match.group(1).strip(' -')
                    date_reported_str = main_match.group(2).strip()
                    
                    # Text after the main match might contain residents affected
                    remaining_text = full_text[main_match.end():].strip()
                    affected_match = re.search(r'(?:Approx\.?|Estimated)\s*([\d,]+)\s*Vermonters\s+Affected', remaining_text, re.IGNORECASE)
                    if affected_match:
                        residents_affected_str = affected_match.group(1).replace(',', '')
                else: # Fallback if primary pattern fails - try to find date and link text as org name
                    date_match_anywhere = re.search(date_pattern, full_text)
                    if date_match_anywhere:
                        date_reported_str = date_match_anywhere.group(0).strip()
                        # Org name might be text before date, or link text if link is not generic
                        org_name_candidate = full_text.split(date_reported_str)[0].strip(' -()')
                        if link_tag and link_tag.get_text(strip=True).lower() not in ['notice', 'pdf', 'details', 'letter']:
                            org_name = link_tag.get_text(strip=True)
                        elif org_name_candidate:
                            org_name = org_name_candidate
                        else: # Could be just the link text even if generic
                            org_name = link_tag.get_text(strip=True) if link_tag else "Unknown Entity"
                    elif link_tag : # No date found, use link text as org name
                         org_name = link_tag.get_text(strip=True)


                if not org_name or org_name.lower() in ['notice', 'pdf'] or not date_reported_str:
                    logger.warning(f"Skipping item in '{year_text_full}' due to missing Org Name ('{org_name}') or Date Reported ('{date_reported_str}'). Original text: '{full_text[:100]}'")
                    page_skipped_count += 1
                    continue

                publication_date_iso = parse_date_flexible_vt(date_reported_str)
                if not publication_date_iso:
                    logger.warning(f"Skipping '{org_name}' in '{year_text_full}' due to unparsable reported date: '{date_reported_str}'")
                    page_skipped_count +=1
                    continue
                
                summary = f"Data security breach for {org_name}."
                if residents_affected_str.isdigit():
                    summary += f" Approx. {residents_affected_str} Vermonters affected."
                
                raw_data = {
                    "original_reported_date_string": date_reported_str,
                    "vermonters_affected": residents_affected_str if residents_affected_str.isdigit() else "Not specified",
                    "year_section_on_page": year_text_full,
                    "original_full_text_of_item": full_text[:250]
                }
                raw_data_json = {k: v for k, v in raw_data.items() if v is not None}

                tags = ["vermont_ag", "vt_ag", f"year_{year_for_tag}"]
                
                item_data = {
                    "source_id": SOURCE_ID_VERMONT_AG,
                    "item_url": item_specific_url if item_specific_url else final_url_to_scrape,
                    "title": org_name.strip(' .,;-()'),
                    "publication_date": publication_date_iso,
                    "summary_text": summary,
                    "raw_data_json": raw_data_json,
                    "tags_keywords": list(set(tags))
                }
                
                # TODO: Implement check for existing record

                insert_response = supabase_client.insert_item(**item_data)
                if insert_response:
                    logger.info(f"Successfully inserted item for '{org_name}' from section '{year_text_full}'. URL: {item_data['item_url']}")
                    page_inserted_count += 1
                else:
                    logger.error(f"Failed to insert item for '{org_name}' from section '{year_text_full}'.")

            except Exception as e:
                logger.error(f"Error processing list item in section '{year_text_full}': {li_item.get_text(strip=True)[:150]}. Error: {e}", exc_info=True)
                page_skipped_count +=1
        
        total_processed += page_processed_count
        total_inserted += page_inserted_count
        total_skipped += page_skipped_count

    logger.info(f"Finished processing Vermont AG breaches. Total items processed: {total_processed}. Total items inserted: {total_inserted}. Total items skipped: {total_skipped}")

if __name__ == "__main__":
    logger.info("Vermont AG Data Security Breach Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_vermont_ag_breaches()
        
    logger.info("Vermont AG Data Security Breach Scraper Finished")
