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
NEW_HAMPSHIRE_AG_BREACH_URL = "https://www.doj.nh.gov/consumer/security-breaches/index.htm"
SOURCE_ID_NEW_HAMPSHIRE_AG = 13

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_flexible_nh(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', 'ongoing', 'see letter', '']:
        return None
    try:
        # Example: "1/1/2023" or "January 1, 2023"
        dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def process_new_hampshire_ag_breaches():
    """
    Fetches New Hampshire AG security breach notifications, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting New Hampshire AG Security Breach Notification processing...")

    try:
        response = requests.get(NEW_HAMPSHIRE_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching New Hampshire AG breach data page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # New Hampshire AG site structure (doj.nh.gov):
    # Data is typically within a main content area.
    # The page lists breaches, often grouped by year under headers (e.g., <h2>2023 Security Breaches</h2>).
    # Each breach notification is usually a list item <li> or a paragraph <p>.
    # These items contain the organization name, date reported, and a link to the PDF notice.
    
    # Find the main content area where breach lists are located.
    # Common DOJ NH site structure might use <div class="inside-copy"> or similar.
    content_area = soup.find('div', class_='inside-copy') # Specific to NH DOJ site structure
    if not content_area:
        # Fallback to a more generic content div or whole page if specific class not found
        content_area = soup.find('div', id='content') or soup.find('main') or soup
        logger.info("Using a fallback content area or whole page as 'div.inside-copy' not found.")


    # Find all year headers to iterate through sections
    # Year headers are usually <h2> like "2023 Security Breaches"
    year_headers = content_area.find_all(['h2', 'h3'], string=re.compile(r'\d{4}\s+Security\s+Breaches', re.IGNORECASE))

    if not year_headers:
        logger.warning("No year-based headers found. Attempting to find breach list items directly in the content area.")
        # If no year headers, assume all relevant <li> or <p> items in content_area are breaches.
        # This requires a different way to collect items.
        # For now, let's assume the primary structure involves year headers.
        # If this needs to be more robust, collect all relevant <li> or <p> directly.
        # Example: all_list_items = content_area.find_all('li')
        # For now, if no year_headers, we will effectively process nothing with the loop below.
        # A better fallback would be to create a dummy year_header for "Current Page" and process all found items.
        class DummyHeader:
            def __init__(self, text, element_source):
                self.text = text
                self.element_source = element_source # e.g. the content_area itself
            def find_next_siblings(self, name): return [] # No siblings for this dummy
            def find_all_next(self, name): # Find all elements of type 'name' within its source
                return self.element_source.find_all(name)


        # Try to find list items directly if no year headers
        direct_list_items = content_area.find_all('li')
        if direct_list_items and any(li.find('a', href=re.compile(r'\.pdf$', re.IGNORECASE)) for li in direct_list_items):
             logger.info(f"No year headers, but found {len(direct_list_items)} list items directly. Processing them under 'Uncategorized Year'.")
             year_headers = [DummyHeader("Uncategorized Year Security Breaches", content_area)] # Process these items
        else:
            logger.error("No year-based headers and no direct list of breach items found. Cannot proceed.")
            return


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
        year_match = re.search(r'(\d{4})', header.text)
        year_text = year_match.group(1) if year_match else "Uncategorized Year"
        logger.info(f"Processing breaches for year section: {year_text}")

        # Breach notifications are usually in <ul> following the header, each breach an <li>.
        # Or sometimes in <p> tags.
        
        breach_items = []
        if isinstance(header, DummyHeader): # Fallback scenario
            # Get all <li> under the source element of the dummy header
            list_items = header.element_source.find_all('li')
            for li in list_items:
                if li.find('a', href=re.compile(r'\.pdf$', re.IGNORECASE)): # Check if it looks like a breach item
                    breach_items.append(li)
        else: # Standard processing with year headers
            # Find the next <ul> or series of <p> tags.
            # NH DOJ often uses <ul> directly after the header.
            ul_list = header.find_next_sibling('ul')
            if ul_list:
                breach_items = ul_list.find_all('li')
            else: # If no <ul>, check for <p> tags that might contain breaches
                current_element = header
                while True:
                    current_element = current_element.find_next_sibling()
                    if not current_element or current_element.name in ['h2', 'h3']: # Stop at next header or end
                        break
                    if current_element.name == 'p' and current_element.find('a', href=re.compile(r'\.pdf$', re.IGNORECASE)):
                        breach_items.append(current_element) # Add paragraph as a breach item
        
        if not breach_items:
            logger.info(f"No breach items (<li> or <p> with PDF links) found for year section '{year_text}'.")
            continue

        logger.info(f"Found {len(breach_items)} potential breach notifications in section '{year_text}'.")
        
        page_processed_count = 0
        page_inserted_count = 0
        page_skipped_count = 0

        # Structure of <li> or <p>:
        # Org Name - Date Reported to AG (Link to PDF on Org Name or separately)
        # Example: "Company X - January 1, 2023 (PDF)"
        # Or: "Company Y (January 1, 2023) (PDF)"

        for item_idx, item_tag in enumerate(breach_items):
            page_processed_count += 1
            try:
                link_tag = item_tag.find('a', href=re.compile(r'\.pdf$', re.IGNORECASE))
                if not link_tag:
                    logger.debug(f"Skipping item in section '{year_text}' as it contains no PDF link: {item_tag.get_text(strip=True)[:100]}")
                    page_skipped_count += 1
                    continue

                item_specific_url = urljoin(NEW_HAMPSHIRE_AG_BREACH_URL, link_tag['href'])
                
                # Extract Org Name and Date from the text of the <li> or <p>
                # The link_tag's text itself might sometimes be "PDF" or "Notice", not the org name.
                # The full text of the item_tag (excluding children like <span> if any) is usually better.
                
                # Get text directly from item_tag, excluding link's own text if it's generic like "PDF"
                item_text_content = item_tag.get_text(separator=' ', strip=True)
                
                # Clean the text: remove the link's text if it's just "PDF" or "Notice", etc.
                # to avoid it being part of date or org name.
                # This is tricky. A common pattern is "Org Name - Date (PDF)".
                # If link_tag.string is "PDF", then item_tag.text might be "Org Name - Date PDF"
                
                # Simpler: remove all link texts first, then parse
                temp_soup = BeautifulSoup(str(item_tag), 'html.parser') # Create temp copy to modify
                for a in temp_soup.find_all('a'): a.decompose() # Remove all links
                cleaned_text = temp_soup.get_text(separator=' ', strip=True)


                # Regex to find date (e.g., Month Day, Year or MM/DD/YYYY)
                # And separate Organization Name. Often "Org Name - Date" or "Org Name (Date)"
                org_name = None
                date_reported_str = None
                
                # Try pattern: "Org Name - Date" (most common)
                # Date can be complex, e.g. "Month D, YYYY" or "MM/DD/YY"
                # Regex for date: (\b(?:Jan(?:uary)?|Feb(?:ruary)?|...|Dec(?:ember)?)\s+\d{1,2},\s+\d{4}\b|\d{1,2}/\d{1,2}/\d{2,4})
                date_pattern_text = r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"
                
                match = re.search(fr'^(.*?)\s*-\s*({date_pattern_text})$', cleaned_text, re.IGNORECASE)
                if match:
                    org_name = match.group(1).strip()
                    date_reported_str = match.group(2).strip()
                else: # Try pattern: "Org Name (Date)"
                    match = re.search(fr'^(.*?)\s*\(\s*({date_pattern_text})\s*\)$', cleaned_text, re.IGNORECASE)
                    if match:
                        org_name = match.group(1).strip()
                        date_reported_str = match.group(2).strip()
                    else: # If no clear separator, assume date is at the end, rest is org name
                        date_match = re.search(date_pattern_text, cleaned_text, re.IGNORECASE)
                        if date_match:
                            date_reported_str = date_match.group(0).strip()
                            org_name = cleaned_text.replace(date_reported_str, '').strip(' -()')
                        else: # No date found in text, org_name is the whole cleaned_text
                            org_name = cleaned_text
                
                # If org_name is empty and link text was descriptive, use that
                if not org_name or len(org_name) < 2:
                     link_text_desc = link_tag.get_text(strip=True)
                     if link_text_desc.lower() not in ['pdf', 'notice', 'security breach notice', 'letter']:
                         org_name = link_text_desc


                if not org_name or not date_reported_str:
                    logger.warning(f"Skipping item in '{year_text}' due to missing Org Name ('{org_name}') or Date Reported ('{date_reported_str}'). Original text: '{item_tag.get_text(strip=True)[:100]}'")
                    page_skipped_count += 1
                    continue

                publication_date_iso = parse_date_flexible_nh(date_reported_str)
                if not publication_date_iso:
                    logger.warning(f"Skipping '{org_name}' in '{year_text}' due to unparsable reported date: '{date_reported_str}'")
                    page_skipped_count +=1
                    continue
                
                summary = f"Security breach notification for {org_name} reported to NH AG."
                # Other details (date of breach, # affected) are usually in the PDF.

                raw_data = {
                    "original_reported_date": date_reported_str,
                    "year_section_on_page": year_text,
                    "original_text_of_item": item_tag.get_text(strip=True)[:250]
                }
                raw_data_json = {k: v for k, v in raw_data.items() if v is not None}

                tags = ["new_hampshire_ag", "nh_ag", f"year_{year_text}"]
                
                item_data = {
                    "source_id": SOURCE_ID_NEW_HAMPSHIRE_AG,
                    "item_url": item_specific_url, # PDF is the specific item
                    "title": org_name,
                    "publication_date": publication_date_iso,
                    "summary_text": summary,
                    "raw_data_json": raw_data_json,
                    "tags_keywords": list(set(tags))
                }
                
                # TODO: Implement check for existing record (e.g., by item_url)

                insert_response = supabase_client.insert_item(**item_data)
                if insert_response:
                    logger.info(f"Successfully inserted item for '{org_name}' from section '{year_text}'. PDF: {item_specific_url}")
                    page_inserted_count += 1
                else:
                    logger.error(f"Failed to insert item for '{org_name}' from section '{year_text}'.")

            except Exception as e:
                logger.error(f"Error processing item in section '{year_text}': {item_tag.get_text(strip=True)[:150]}. Error: {e}", exc_info=True)
                page_skipped_count +=1
        
        total_processed += page_processed_count
        total_inserted += page_inserted_count
        total_skipped += page_skipped_count

    logger.info(f"Finished processing New Hampshire AG breaches. Total items processed: {total_processed}. Total items inserted: {total_inserted}. Total items skipped: {total_skipped}")

if __name__ == "__main__":
    logger.info("New Hampshire AG Security Breach Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_new_hampshire_ag_breaches()
        
    logger.info("New Hampshire AG Security Breach Scraper Finished")
