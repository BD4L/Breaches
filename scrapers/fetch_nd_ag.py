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
NORTH_DAKOTA_AG_BREACH_URL = "https://attorneygeneral.nd.gov/consumer-resources/data-breach-notices"
SOURCE_ID_NORTH_DAKOTA_AG = 15

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_flexible_nd(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', 'ongoing', 'see letter', '']:
        return None
    try:
        dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def process_north_dakota_ag_breaches():
    """
    Fetches North Dakota AG data breach notices, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting North Dakota AG Data Breach Notice processing...")

    try:
        response = requests.get(NORTH_DAKOTA_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching North Dakota AG breach data page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # North Dakota AG site structure (attorneygeneral.nd.gov):
    # Data is typically within a main content area.
    # The page lists breaches by year, often under accordion-style toggles (e.g., "2023 Data Breach Notices").
    # Inside each year's section, there's usually a list (<ul>) of links to PDF notices.
    # Each list item <li> contains the link, and the link text is the entity name + date.
    
    # Find all year sections/accordions. Common pattern is a div or similar element for each year.
    # Example: <div class="panel panel-default"> <div class="panel-heading"><h4 class="panel-title"><a data-toggle="collapse">2023 Data Breach Notices</a></h4></div> <div class="panel-collapse collapse"><ul>...</ul></div></div>
    # Or simpler hX + ul structure.
    
    year_sections = []
    # Try to find panel/accordion items first (common Bootstrap pattern)
    panel_items = soup.select("div.panel.panel-default")
    if panel_items:
        for item in panel_items:
            panel_heading = item.find('div', class_="panel-heading")
            panel_collapse = item.find('div', class_="panel-collapse")
            if panel_heading and panel_collapse:
                # Title for year is usually in an <a> tag within h4.panel-title
                year_title_tag = panel_heading.find(['h4', 'h3', 'h2'], class_="panel-title")
                if year_title_tag and year_title_tag.find('a'):
                    year_text = year_title_tag.find('a').get_text(strip=True)
                    year_sections.append({'year_text': year_text, 'list_container': panel_collapse})
    
    if not year_sections:
        # Fallback: Look for hX tags with "YYYY Data Breach Notices" and assume <ul> follows
        year_headers = soup.find_all(['h2', 'h3', 'h4'], string=re.compile(r'\d{4}\s+Data\s+Breach\s+Notices', re.IGNORECASE))
        if year_headers:
            for header in year_headers:
                ul_list = header.find_next_sibling('ul')
                if not ul_list : # Try one more level down if wrapped in a div
                    next_div = header.find_next_sibling('div')
                    if next_div: ul_list = next_div.find('ul')
                
                if ul_list:
                    year_sections.append({'year_text': header.get_text(strip=True), 'list_container': ul_list})
        else: # If no year headers, maybe there's just one main list on the page
            main_list = soup.find('ul') # A very generic fallback
            # Check if this list seems to contain breach notices (e.g. li with PDF links)
            if main_list and main_list.find('li') and main_list.find('li').find('a', href=re.compile(r'\.pdf$', re.IGNORECASE)):
                logger.info("No yearly sections found, attempting to process a single main list on the page.")
                year_sections.append({'year_text': "Current Page Data", 'list_container': main_list})


    if not year_sections:
        logger.error("Could not find any year sections or a main list for breach notifications. Page structure might have changed.")
        # logger.debug(f"Page content sample (first 1000 chars): {response.text[:1000]}")
        return
        
    logger.info(f"Found {len(year_sections)} year sections to process.")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    total_processed = 0
    total_inserted = 0
    total_skipped = 0
    
    for section in year_sections:
        year_text_full = section['year_text'] # e.g., "2023 Data Breach Notices"
        list_container = section['list_container'] # This should contain the <ul>
        
        ul_element = list_container if list_container.name == 'ul' else list_container.find('ul')
        if not ul_element:
            logger.warning(f"No <ul> element found in section '{year_text_full}'. Skipping this section.")
            continue
            
        notifications = ul_element.find_all('li')

        if not notifications:
            logger.info(f"No breach notification list items (<li>) found in section '{year_text_full}'.")
            continue
        
        year_match = re.search(r'(\d{4})', year_text_full)
        year_for_tag = year_match.group(1) if year_match else "unknown_year"
        logger.info(f"Found {len(notifications)} potential breach notifications in section '{year_text_full}' (Year: {year_for_tag}).")
        
        page_processed_count = 0
        page_inserted_count = 0
        page_skipped_count = 0

        # Structure of <li>:
        # <a href="link_to.pdf">Entity Name - Date Reported</a>
        # Or: Entity Name (Date Reported) <a href="link_to.pdf">PDF</a>

        for item_idx, li_item in enumerate(notifications):
            page_processed_count += 1
            try:
                link_tag = li_item.find('a', href=re.compile(r'\.pdf$', re.IGNORECASE))
                if not link_tag:
                    logger.debug(f"Skipping item in section '{year_text_full}' as it contains no PDF link: {li_item.get_text(strip=True)[:100]}")
                    page_skipped_count += 1
                    continue

                item_specific_url = urljoin(NORTH_DAKOTA_AG_BREACH_URL, link_tag['href'])
                
                # Text for parsing Org Name and Date is usually the link_tag's text or the li_item's full text.
                # If link_tag text is "PDF" or "Notice", then full <li> text is needed.
                text_to_parse = link_tag.get_text(strip=True)
                if text_to_parse.lower() in ['pdf', 'notice', 'view notice', 'breach letter']:
                    text_to_parse = li_item.get_text(strip=True) # Use full <li> text

                # Regex to find date and separate Organization Name.
                # Common patterns: "Org Name - Date", "Org Name (Date)"
                org_name = None
                date_reported_str = None
                
                # Date pattern: MM/DD/YYYY or Month Day, Year
                date_pattern_text = r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"
                
                # Try "Org Name - Date"
                match = re.search(fr'^(.*?)\s*-\s*({date_pattern_text})$', text_to_parse, re.IGNORECASE)
                if match:
                    org_name = match.group(1).strip()
                    date_reported_str = match.group(2).strip()
                else: # Try "Org Name (Date)"
                    match = re.search(fr'^(.*?)\s*\(\s*({date_pattern_text})\s*\)$', text_to_parse, re.IGNORECASE)
                    if match:
                        org_name = match.group(1).strip()
                        date_reported_str = match.group(2).strip()
                    else: # If no clear separator, assume date is at the end, rest is org name
                        date_match = re.search(date_pattern_text, text_to_parse, re.IGNORECASE)
                        if date_match:
                            date_reported_str = date_match.group(0).strip()
                            org_name = text_to_parse.replace(date_reported_str, '').strip(' -()')
                        else: # No date found in text, org_name is the whole text_to_parse
                            org_name = text_to_parse.strip() # Clean any surrounding spaces or hyphens if it was just name

                # Clean org_name from common PDF artifacts if it was the full text_to_parse
                if org_name:
                    org_name = org_name.replace("(PDF)", "").replace("PDF", "").strip(' -()')

                if not org_name or not date_reported_str:
                    logger.warning(f"Skipping item in '{year_text_full}' due to missing Org Name ('{org_name}') or Date Reported ('{date_reported_str}'). Original text: '{text_to_parse[:100]}'")
                    page_skipped_count += 1
                    continue

                publication_date_iso = parse_date_flexible_nd(date_reported_str)
                if not publication_date_iso:
                    logger.warning(f"Skipping '{org_name}' in '{year_text_full}' due to unparsable reported date: '{date_reported_str}'")
                    page_skipped_count +=1
                    continue
                
                summary = f"Data breach notification for {org_name} reported to ND AG."
                # Other details (date of breach, # affected, type of info) are usually in the PDF.

                raw_data = {
                    "original_reported_date_string": date_reported_str,
                    "year_section_on_page": year_text_full, # e.g. "2023 Data Breach Notices"
                    "original_text_of_item": li_item.get_text(strip=True)[:250]
                }
                raw_data_json = {k: v for k, v in raw_data.items() if v is not None}

                tags = ["north_dakota_ag", "nd_ag", f"year_{year_for_tag}"]
                
                item_data = {
                    "source_id": SOURCE_ID_NORTH_DAKOTA_AG,
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
                    logger.info(f"Successfully inserted item for '{org_name}' from section '{year_text_full}'. PDF: {item_specific_url}")
                    page_inserted_count += 1
                else:
                    logger.error(f"Failed to insert item for '{org_name}' from section '{year_text_full}'.")

            except Exception as e:
                logger.error(f"Error processing list item in section '{year_text_full}': {li_item.get_text(strip=True)[:150]}. Error: {e}", exc_info=True)
                page_skipped_count +=1
        
        total_processed += page_processed_count
        total_inserted += page_inserted_count
        total_skipped += page_skipped_count

    logger.info(f"Finished processing North Dakota AG breaches. Total items processed: {total_processed}. Total items inserted: {total_inserted}. Total items skipped: {total_skipped}")

if __name__ == "__main__":
    logger.info("North Dakota AG Data Breach Notice Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_north_dakota_ag_breaches()
        
    logger.info("North Dakota AG Data Breach Notice Scraper Finished")
