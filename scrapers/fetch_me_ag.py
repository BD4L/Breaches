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
MAINE_AG_BREACH_URL = "https://www.maine.gov/ag/consumer/identity_theft/index.shtml"
SOURCE_ID_MAINE_AG = 9

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_flexible_me(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', 'ongoing']:
        return None
    try:
        # Handle cases like "1/1/2023 & 2/1/2023" - take the first date.
        date_str_cleaned = date_str.split('&')[0].split('and')[0].strip()
        dt_object = dateutil_parser.parse(date_str_cleaned)
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def process_maine_ag_breaches():
    """
    Fetches Maine AG security breach notifications, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting Maine AG Security Breach Notification processing...")

    try:
        # The initial URL might redirect to one with 'Public' in the path.
        # e.g. https://www.maine.gov/ag/consumer/identity_theft/Public_SecurityBreachInformation.shtml
        session = requests.Session()
        response = session.get(MAINE_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30, allow_redirects=True)
        response.raise_for_status()
        final_url = response.url # Use the URL after any redirects
        logger.info(f"Fetched data from URL (after potential redirects): {final_url}")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Maine AG breach data page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Maine AG site structure (as of early 2024):
    # Data is within a main content area, often <div class="content"> or similar.
    # Breach notifications are usually listed under year-based headers (e.g., <h2>2023 Security Breaches</h2>).
    # Each notification is a paragraph <p> containing:
    #   - Organization Name (sometimes as <strong> or <b>)
    #   - Date of Notice to AG (e.g., "Notice to AG: 1/1/2023")
    #   - Date of Breach (e.g., "Date of Breach: 12/15/2022")
    #   - Link to the actual notice (PDF or webpage)
    # Sometimes the format varies slightly.

    # Find the main content area. Common for maine.gov sites.
    # content_div = soup.find('div', class_='center-content') # A common class
    # if not content_div:
    #     content_div = soup.find('div', id='content') # Another common ID
    # if not content_div:
    #     logger.warning("Could not find a specific content div ('center-content' or 'id=content'). Searching whole page. This might be less accurate.")
    content_div = soup # Search whole page if specific content div not found or too restrictive

    # Find all year headers to iterate through sections
    # Year headers are usually <h2> or <h3> like "2024 Security Breaches"
    year_headers = content_div.find_all(['h2', 'h3'], string=re.compile(r'\d{4}\s+Security\s+Breaches', re.IGNORECASE))

    if not year_headers:
        logger.error("No year-based headers found (e.g., '2023 Security Breaches'). Page structure might have changed significantly. Attempting to find individual notices directly.")
        # As a fallback, try to find all <p> tags that look like breach notices if no year headers
        # This is less structured and might be prone to errors.
        # For now, let's assume year headers are the primary way to find breach lists.
        # If this path is taken, ensure logic below can handle it (e.g. year_text = "Unknown Year")
        # and that `find_next_siblings('p')` or similar is adjusted.
        # For now, we will rely on year_headers for structure.
        # If you want to process without year headers, you'd collect all <p> tags under content_div.
        # all_paragraphs = content_div.find_all('p') # And then filter these.
        # return # Or proceed with all_paragraphs if that logic is implemented.
        # For now, let's assume the structure with year headers is key.
        # If they are truly gone, the scraper needs a major rethink for how to find breach <p> elements.
        # One option: find all <p> with an <a> tag whose href contains "SecurityBreach" or ".pdf"
        # and also contains text like "Notice to AG:"
        
        # Let's try a direct search for paragraphs that seem like breach notifications
        # This is a fallback if year_headers are not found.
        potential_breach_paragraphs = []
        for p_tag in content_div.find_all('p'):
            text_content = p_tag.get_text(separator=" ", strip=True)
            if "Notice to AG:" in text_content and p_tag.find('a', href=True):
                potential_breach_paragraphs.append(p_tag)
        
        if not potential_breach_paragraphs:
            logger.error("Fallback: No paragraphs resembling breach notifications found directly either. Cannot proceed.")
            return
        else:
            logger.info(f"Fallback: Found {len(potential_breach_paragraphs)} potential breach paragraphs directly (no year headers).")
            # Process these paragraphs directly, assuming no year context from headers.
            # This means year_text would be "Unknown" or derived differently if possible.
            # We'll create a dummy year_headers list to make the loop below work.
            # This is a simplified way to integrate the fallback.
            class DummyHeader:
                def __init__(self, text):
                    self.text = text
                def find_next_siblings(self, name): # Simulate finding paragraphs after this "header"
                    if name == 'p':
                        # This needs to be smarter; it should only return paragraphs until the next "dummy header"
                        # For a single list of paragraphs, we just return all of them once.
                        if not hasattr(self, 'processed_fallback_paras'):
                            setattr(self, 'processed_fallback_paras', True)
                            return potential_breach_paragraphs
                    return []

            year_headers = [DummyHeader("Unknown Year - Fallback Processing")]


    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    inserted_count = 0
    processed_count = 0
    skipped_count = 0

    for header in year_headers:
        year_match = re.search(r'(\d{4})', header.text)
        year_text = year_match.group(1) if year_match else "Unknown Year"
        logger.info(f"Processing breaches for year section: {year_text}")

        # Breach notifications are usually in <p> tags immediately following the year header,
        # until the next header or end of content.
        current_element = header
        while True:
            current_element = current_element.find_next_sibling()
            if not current_element: # No more siblings
                break
            if current_element.name in ['h2', 'h3', 'h4']: # Reached next header
                break
            if current_element.name != 'p': # Only interested in paragraph tags
                continue

            # Now `current_element` is a <p> tag potentially containing a breach.
            p_tag = current_element
            processed_count += 1
            
            try:
                link_tag = p_tag.find('a', href=True)
                if not link_tag:
                    logger.debug(f"Skipping paragraph in section '{year_text}' as it contains no link: {p_tag.get_text(strip=True)[:100]}")
                    skipped_count += 1
                    continue

                item_specific_url = urljoin(final_url, link_tag['href'])
                
                # Extracting text content from the paragraph
                # The structure can be: <strong>Org Name</strong> Notice to AG: MM/DD/YYYY. Date of Breach: MM/DD/YYYY <a href="...">Notice</a>
                # Or Org Name (Notice to AG: MM/DD/YYYY; Date of Breach: MM/DD/YYYY) <a href="...">Notice</a>
                
                # Get all text, separating by a unique marker to handle cases where org name is not bold/strong
                # Then remove link text to avoid it being part of org name or dates.
                if link_tag.string: # Remove link's own text from paragraph text
                    link_text_to_remove = link_tag.get_text(strip=True)
                    # Use a placeholder for the link to effectively remove its text for parsing
                    link_tag.string = "__LINK_PLACEHOLDER__" 
                
                full_text = p_tag.get_text(separator=" ", strip=True).replace("__LINK_PLACEHOLDER__", "")


                org_name = None
                # Try to get org_name from <strong> or <b> tag first
                strong_tag = p_tag.find(['strong', 'b'])
                if strong_tag:
                    org_name = strong_tag.get_text(strip=True)
                    # Remove org_name from full_text to make date extraction easier
                    full_text = full_text.replace(org_name, "", 1).strip()
                
                # Regex to find dates
                date_notice_ag_str = None
                date_breach_str = None

                # Pattern: "Notice to AG: MM/DD/YYYY" or "Notice to AG MM/DD/YYYY"
                notice_ag_match = re.search(r'Notice\s+to\s+AG:?\s*([\d/]+(?:\s*-\s*[\d/]+)?)', full_text, re.IGNORECASE)
                if notice_ag_match:
                    date_notice_ag_str = notice_ag_match.group(1).strip()
                    if not org_name: # If org_name wasn't in bold, it's text before "Notice to AG"
                        org_name = full_text.split(notice_ag_match.group(0))[0].strip(' .-')

                # Pattern: "Date of Breach: MM/DD/YYYY" or "Breach Dates: MM/DD/YYYY - MM/DD/YYYY"
                breach_date_match = re.search(r'(?:Date(?:s)?\s+of\s+Breach|Breach\s+Date(?:s)?):?\s*([\d/,-]+(?:\s*-\s*[\d/,-]+)?)', full_text, re.IGNORECASE)
                if breach_date_match:
                    date_breach_str = breach_date_match.group(1).strip()
                    if not org_name and not notice_ag_match: # If no bold and no AG notice, text before breach date
                         org_name = full_text.split(breach_date_match.group(0))[0].strip(' .-')
                
                # If org_name is still not found (e.g., if dates are missing or format is very different)
                # Fallback: use the link text if it's not generic, or the text before the first recognized pattern.
                if not org_name or len(org_name) < 3 : # Check for very short or missing org_name
                    # Try to get it from link_text if link_text is descriptive
                    link_text_cleaned = link_tag.get_text(strip=True)
                    if link_text_cleaned.lower() not in ["notice", "security breach notice", "view notice", "details", "pdf"]:
                        org_name = link_text_cleaned
                    else: # Last resort: whatever text is left in full_text, or "Unknown Entity"
                        # Clean up common phrases if they are the only thing left
                        cleaned_full_text = full_text
                        if notice_ag_match: cleaned_full_text = cleaned_full_text.replace(notice_ag_match.group(0), "").strip()
                        if breach_date_match: cleaned_full_text = cleaned_full_text.replace(breach_date_match.group(0), "").strip()
                        cleaned_full_text = cleaned_full_text.strip(' .,;-()')
                        if len(cleaned_full_text) > 3 : # Use if it's somewhat substantial
                            org_name = cleaned_full_text
                        else:
                            org_name = f"Unknown Entity ({year_text})"


                if not org_name or org_name.startswith("Unknown Entity"):
                    logger.warning(f"Skipping paragraph in section '{year_text}' due to missing or unclear Organization Name. Text: {p_tag.get_text(strip=True)[:100]}")
                    skipped_count += 1
                    continue

                # Prioritize notice to AG date for publication_date
                publication_date_iso = parse_date_flexible_me(date_notice_ag_str)
                if not publication_date_iso: # Fallback to breach date if AG notice date not found/parsable
                    publication_date_iso = parse_date_flexible_me(date_breach_str.split('-')[0].strip() if date_breach_str else None) 
                
                if not publication_date_iso: # If still no date, try using the year from header (Jan 1st)
                    if year_text != "Unknown Year":
                        publication_date_iso = parse_date_flexible_me(f"January 1, {year_text}")
                        logger.info(f"Used Jan 1 of year '{year_text}' as fallback publication date for '{org_name}'.")
                    else:
                        logger.warning(f"Skipping '{org_name}' in section '{year_text}' due to no parsable date. AG: '{date_notice_ag_str}', Breach: '{date_breach_str}'")
                        skipped_count +=1
                        continue
                
                summary = f"Security breach notification for {org_name}."
                if date_breach_str: summary += f" Date of Breach: {date_breach_str}."
                if date_notice_ag_str: summary += f" Notified AG: {date_notice_ag_str}."
                # Maine AG page does not typically list # affected or type of breach on the list page.

                raw_data = {
                    "original_text_snippet": p_tag.get_text(strip=True)[:250], # Store snippet for reference
                    "date_notice_to_ag": date_notice_ag_str if date_notice_ag_str else "Not specified",
                    "date_of_breach": date_breach_str if date_breach_str else "Not specified",
                    "year_section_on_page": year_text
                }
                raw_data_json = {k: v for k, v in raw_data.items() if v is not None}

                tags = ["maine_ag", "me_breach", f"year_{year_text}"]
                
                item_data = {
                    "source_id": SOURCE_ID_MAINE_AG,
                    "item_url": item_specific_url,
                    "title": org_name.strip(' .,;-'),
                    "publication_date": publication_date_iso,
                    "summary_text": summary.strip(),
                    "raw_data_json": raw_data_json,
                    "tags_keywords": list(set(tags))
                }
                
                # TODO: Implement check for existing record

                insert_response = supabase_client.insert_item(**item_data)
                if insert_response:
                    logger.info(f"Successfully inserted item for '{org_name}' from year '{year_text}'. URL: {item_specific_url}")
                    inserted_count += 1
                else:
                    logger.error(f"Failed to insert item for '{org_name}' from year '{year_text}'.")

            except Exception as e:
                logger.error(f"Error processing paragraph in section '{year_text}': {p_tag.get_text(strip=True)[:150]}. Error: {e}", exc_info=True)
                skipped_count +=1
    
    # This part is for the fallback scenario where year_headers were not found initially
    # and `potential_breach_paragraphs` were processed directly.
    # The loop above with `DummyHeader` handles this.
    if not year_headers or (len(year_headers) == 1 and year_headers[0].text == "Unknown Year - Fallback Processing" and not hasattr(year_headers[0], 'processed_fallback_paras') ):
         logger.info("No year headers were initially found or processed with the main loop. Fallback paragraph processing should have occurred if paragraphs were found.")


    logger.info(f"Finished processing Maine AG breaches. Total items processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("Maine AG Security Breach Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_maine_ag_breaches()
        
    logger.info("Maine AG Security Breach Scraper Finished")
