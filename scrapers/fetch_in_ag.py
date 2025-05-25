import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin, unquote
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
INDIANA_AG_BREACH_URL = "https://www.in.gov/attorneygeneral/2874.htm" # This is the listing page
# The actual data is often loaded from a different URL or via JS.
# After inspection, it seems the links point to PDFs which are the notices.
# The page lists breaches by year.
SOURCE_ID_INDIANA_AG = 7

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_flexible_in(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided']:
        return None
    try:
        # Example: "January 1, 2023"
        dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def extract_date_from_text(text: str) -> str | None:
    """
    Attempts to extract a date from a text string that might contain it.
    Example: "XYZ Corp (Notice Date 1/1/2023)"
    This is a helper and might need to be more robust.
    """
    import re
    # Regex to find dates like MM/DD/YYYY or Month DD, YYYY etc.
    # This is a basic regex, more complex ones might be needed.
    date_patterns = [
        r'(\d{1,2}/\d{1,2}/\d{2,4})', # MM/DD/YYYY or MM/DD/YY
        r'(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},\s+\d{4}\b)', # Month DD, YYYY
        r'(\d{1,2}-\d{1,2}-\d{2,4})', # MM-DD-YYYY
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            return parse_date_flexible_in(match.group(1))
    return None


def process_indiana_ag_breaches():
    """
    Fetches Indiana AG security breach notifications, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting Indiana AG Security Breach Notification processing...")

    try:
        response = requests.get(INDIANA_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Indiana AG breach data page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Indiana AG site structure:
    # The page at https://www.in.gov/attorneygeneral/2874.htm has links grouped by year.
    # Each link typically goes directly to a PDF notice.
    # The text of the link is usually the Organization Name, sometimes with a date.
    # We need to find these links. They are usually within a content div, like 'div#contentcontainer'.
    
    content_area = soup.find('div', id='contentcontainer') # Main content area for this site
    if not content_area:
        content_area = soup.find('article', class_='main-content') # Fallback for other IN.gov pages
        if not content_area:
            logger.error("Could not find the main content area ('div#contentcontainer' or 'article.main-content'). Page structure may have changed.")
            # logger.debug(f"Page content sample (first 1000 chars): {response.text[:1000]}")
            return

    # Find all PDF links within this area. These are the breach notices.
    # Links are usually <a> tags with href ending in .pdf.
    # They might be inside <p> or <li> tags.
    
    # Look for sections by year, often in <h2> or <h3> tags like "2023 Data Breach Notifications"
    # For now, let's grab all PDF links in the content area.
    # We might need to refine if there are other non-breach PDFs.

    pdf_links = content_area.find_all('a', href=lambda href: href and href.lower().endswith('.pdf'))
    
    logger.info(f"Found {len(pdf_links)} potential PDF breach notifications on the page.")

    if not pdf_links:
        logger.warning("No PDF links found in the content area. Check page structure and link format.")
        return

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    inserted_count = 0
    processed_count = 0
    skipped_count = 0

    for link_tag in pdf_links:
        processed_count += 1
        try:
            item_specific_url = urljoin(INDIANA_AG_BREACH_URL, link_tag['href'])
            # The link text is usually the organization name, possibly with a date.
            link_text = link_tag.get_text(strip=True)
            
            org_name = link_text
            publication_date_iso = None

            # Try to extract date from link text, e.g., "Org Name (1/1/23)" or "Org Name (Notice Date: Jan 1, 2023)"
            # This part is heuristic.
            # Common patterns: "Org Name (1/1/23)", "Org Name - 1/1/23", "Org Name Notice 1/1/23"
            # A more robust way might be to look at the PDF's last modified date if available, or metadata,
            # but that requires fetching each PDF. For now, rely on link text or surrounding text.

            # Attempt to parse date from link text itself
            publication_date_iso = extract_date_from_text(link_text)
            
            # If date found in link text, try to clean org_name
            if publication_date_iso:
                # Remove common date patterns or "Notice Date" parts from org_name
                # This is tricky and might need several regexes
                org_name = re.sub(r'\s*\(\s*\d{1,2}/\d{1,2}/\d{2,4}\s*\)\s*$', '', org_name, flags=re.IGNORECASE).strip()
                org_name = re.sub(r'\s*-\s*\d{1,2}/\d{1,2}/\d{2,4}\s*$', '', org_name, flags=re.IGNORECASE).strip()
                org_name = re.sub(r'\s*\(Notice Date:?\s*.*?\)\s*$', '', org_name, flags=re.IGNORECASE).strip()
                org_name = re.sub(r'\s*Notice Date:?\s*.*$', '', org_name, flags=re.IGNORECASE).strip()


            # If no date from link text, check parent elements or siblings for year context
            # Example: Links are under a <h2>2023 Data Breach Notifications</h2>
            if not publication_date_iso:
                year_text = None
                # Check parent <p> or <li>, then headers <h2>, <h3> etc.
                current_element = link_tag.parent
                for _ in range(4): # Check up to 4 levels up for a year header
                    if current_element:
                        # Check previous sibling headers for year
                        prev_sibling_header = current_element.find_previous_sibling(['h2', 'h3', 'h4'])
                        if prev_sibling_header and "Data Breach Notification" in prev_sibling_header.get_text():
                            year_match = re.search(r'\b(20\d{2})\b', prev_sibling_header.get_text())
                            if year_match:
                                year_text = year_match.group(1)
                                # Use Jan 1 of that year as a fallback if no other date
                                publication_date_iso = parse_date_flexible_in(f"January 1, {year_text}") 
                                logger.info(f"Used year '{year_text}' from header for '{org_name}' as fallback date.")
                                break
                        current_element = current_element.parent
                    else:
                        break
            
            if not org_name:
                # Try to derive org name from PDF filename if link text was unhelpful
                # e.g. "MyCorp_Data_Breach_Notification.pdf" -> "MyCorp"
                pdf_filename = os.path.basename(unquote(item_specific_url))
                org_name = pdf_filename.replace('_', ' ').replace('-', ' ')
                # Remove common suffixes
                common_suffixes = ["Data Breach Notification", "Breach Notice", "Notification", ".pdf"]
                for suffix in common_suffixes:
                    org_name = org_name.replace(suffix, "")
                org_name = org_name.strip().title() # Capitalize
                if not org_name: # If still empty, skip
                    logger.warning(f"Skipping link {item_specific_url} as organization name could not be derived.")
                    skipped_count += 1
                    continue


            if not publication_date_iso:
                # As a last resort, if no date can be found/parsed, skip or use current date?
                # For now, we'll skip if no date can be reasonably inferred.
                logger.warning(f"Skipping '{org_name}' (URL: {item_specific_url}) due to missing or unparsable publication date.")
                skipped_count +=1
                continue
            
            # Since details like type of breach or residents affected are in the PDF,
            # we'll have a generic summary for now.
            summary = f"Security breach notification for {org_name}. Details are in the linked PDF."

            raw_data = {
                "original_link_text": link_text,
                "pdf_url": item_specific_url,
                # No other fields are typically available on the list page itself.
            }
            raw_data_json = {k: v for k, v in raw_data.items() if v is not None and v.strip() != ""}

            tags = ["indiana_ag", "in_breach", "pdf_notification"]
            # If PDF content were fetched, more tags could be derived.

            item_data = {
                "source_id": SOURCE_ID_INDIANA_AG,
                "item_url": item_specific_url, # The PDF link is the most specific URL
                "title": org_name,
                "publication_date": publication_date_iso,
                "summary_text": summary,
                "raw_data_json": raw_data_json,
                "tags_keywords": list(set(tags))
            }
            
            # TODO: Implement check for existing record before inserting (e.g., by item_url)

            insert_response = supabase_client.insert_item(**item_data)
            if insert_response:
                logger.info(f"Successfully inserted item for '{org_name}'. URL: {item_specific_url}")
                inserted_count += 1
            else:
                logger.error(f"Failed to insert item for '{org_name}'.")

        except Exception as e:
            # Use link_tag.get('href', 'Unknown URL') in case item_specific_url not yet defined
            logger.error(f"Error processing link: {link_tag.get('href', 'Unknown URL')}. Error: {e}", exc_info=True)
            skipped_count +=1

    logger.info(f"Finished processing Indiana AG breaches. Total links processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("Indiana AG Security Breach Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_indiana_ag_breaches()
        
    logger.info("Indiana AG Security Breach Scraper Finished")
