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
NEW_JERSEY_CYBER_URL = "https://www.cyber.nj.gov/data-breach-alerts"
SOURCE_ID_NEW_JERSEY_CYBER = 14 # Per task instructions, using 14 for NJ (Cybersecurity)

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_flexible_nj(date_str: str) -> str | None:
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

def process_new_jersey_cyber_breaches():
    """
    Fetches New Jersey Cybersecurity data breach alerts, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting New Jersey Cybersecurity Data Breach Alert processing...")

    try:
        response = requests.get(NEW_JERSEY_CYBER_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching New Jersey Cybersecurity breach data page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # New Jersey Cybersecurity site structure (cyber.nj.gov):
    # Data is typically presented as a list of alerts/articles.
    # Each alert might be in a <div> or <article> tag.
    # Need to find the container for these alerts and then iterate through individual items.
    # As of inspection (early 2024), alerts are within <div class="row"> containing <div class="col-md-4"> items,
    # each with a <div class="card">.
    
    # Find the main container for the breach alert cards.
    # The cards seem to be within a <div class="container"> -> <div class="row gx-5">
    # Each card is then <div class="col-md-6 col-lg-4 mb-5"> -> <div class="card h-100 shadow border-0">
    
    alert_cards_container = soup.find('div', class_='row', attrs={'gx-5': True}) # More specific row if possible
    if not alert_cards_container:
        # Fallback to any row that seems to contain cards
        alert_cards_container = soup.find('div', class_='row') 
        if not alert_cards_container :
            logger.error("Could not find the main container for breach alert cards (div.row.gx-5 or div.row). Page structure might have changed.")
            # logger.debug(f"Page content sample (first 1000 chars): {response.text[:1000]}")
            return

    # Find individual alert items (cards)
    # Each card is usually in a <div class="col-md-..."> or similar grid column class.
    # Inside that, a <div class="card">.
    
    # Selects columns that directly contain a card.
    alert_items = alert_cards_container.select("div[class*='col-']:has(div.card)")

    if not alert_items:
        logger.warning("No breach alert items (cards in columns) found within the container. Check selectors or page structure.")
        return
        
    logger.info(f"Found {len(alert_items)} potential breach alert items on the page.")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    inserted_count = 0
    processed_count = 0
    skipped_count = 0
    
    for item_idx, item_col_div in enumerate(alert_items):
        processed_count += 1
        card = item_col_div.find('div', class_='card')
        if not card:
            logger.warning(f"Skipping item #{item_idx+1} as no card div found within column.")
            skipped_count += 1
            continue
            
        try:
            title_tag = card.find(['h2', 'h3', 'h5'], class_='card-title') # Title often in card-title
            if not title_tag: title_tag = card.find('a', class_='text-decoration-none') # Sometimes title is the main link
            
            org_name = title_tag.get_text(strip=True) if title_tag else "Unknown Entity"
            
            # Link to the detailed alert page is usually on the title or a "Read More" button.
            # Prefer a link that seems to go to a sub-page for this alert.
            item_specific_url = None
            # Try link on title first
            if title_tag and title_tag.name == 'a' and title_tag.has_attr('href'):
                item_specific_url = urljoin(NEW_JERSEY_CYBER_URL, title_tag['href'])
            else: # Try any link within the card that looks like a detail page link
                # Avoid mailto or external links not on cyber.nj.gov if possible
                all_links_in_card = card.find_all('a', href=True)
                for link in all_links_in_card:
                    href = link['href']
                    if not href.startswith(('mailto:', 'tel:', 'http://', 'https://')): # Relative link likely internal
                        item_specific_url = urljoin(NEW_JERSEY_CYBER_URL, href)
                        break # Take first good one
                if not item_specific_url and all_links_in_card: # Fallback to first link if only external/absolute are present
                    item_specific_url = urljoin(NEW_JERSEY_CYBER_URL, all_links_in_card[0]['href'])


            # Date is often in a <div class="text-muted fst-italic mb-2"> or <p class="card-text"><small class="text-muted">
            date_str = None
            date_container = card.find('div', class_=re.compile(r'text-muted.*mb-2')) # e.g. text-muted fst-italic mb-2
            if date_container:
                date_str = date_container.get_text(strip=True)
            else: # Try another common pattern for dates in cards
                small_text_muted = card.find('small', class_='text-muted')
                if small_text_muted:
                    date_str = small_text_muted.get_text(strip=True)
            
            # Sometimes date is part of a general <p class="card-text">
            if not date_str:
                card_text_p = card.find('p', class_='card-text')
                if card_text_p:
                    # Try to extract date from this paragraph if it looks like one
                    # This is heuristic. Example: "Posted on January 1, 2023"
                    match = re.search(r'(?:Posted\s+on\s+)?([A-Za-z]+\s+\d{1,2},\s+\d{4})', card_text_p.get_text(strip=True))
                    if match: date_str = match.group(1)


            if not org_name or org_name == "Unknown Entity":
                logger.warning(f"Skipping item #{item_idx+1} due to missing Organization Name. URL: {item_specific_url if item_specific_url else 'N/A'}")
                skipped_count += 1
                continue
            
            publication_date_iso = parse_date_flexible_nj(date_str)
            if not publication_date_iso:
                logger.warning(f"Skipping '{org_name}' due to unparsable or missing date: '{date_str}'. URL: {item_specific_url}")
                skipped_count +=1
                continue
            
            # Summary text can be from <p class="card-text"> (if not used for date)
            summary = ""
            summary_p = card.find('p', class_='card-text')
            if summary_p:
                # Avoid re-capturing date if it was in this p tag
                temp_summary = summary_p.get_text(strip=True)
                if date_str and date_str in temp_summary: # Basic check to avoid date in summary
                    # This could be improved by removing only the date part more cleanly
                    summary = temp_summary.replace(date_str, "").strip()
                else:
                    summary = temp_summary
            if not summary or len(summary) < 20 : # If summary is too short or missing, use a generic one
                summary = f"Cybersecurity alert related to {org_name}."


            raw_data = {
                "original_date_string": date_str,
                "card_html_snippet": card.prettify()[:500] # For debugging structure
                # No specific fields like "residents affected" or "type of breach" on this list page.
                # Those would be on the detail page (item_specific_url), if that were fetched.
            }
            raw_data_json = {k: v for k, v in raw_data.items() if v is not None}

            tags = ["new_jersey_cyber", "nj_cyber", "data_breach_alert"]
            # Basic tagging from title/summary
            combined_text_for_tags = (org_name + " " + summary).lower()
            if "ransomware" in combined_text_for_tags: tags.append("ransomware")
            if "phishing" in combined_text_for_tags: tags.append("phishing")
            if "vulnerability" in combined_text_for_tags: tags.append("vulnerability")
            if "malware" in combined_text_for_tags: tags.append("malware")


            item_data = {
                "source_id": SOURCE_ID_NEW_JERSEY_CYBER,
                "item_url": item_specific_url if item_specific_url else NEW_JERSEY_CYBER_URL,
                "title": org_name,
                "publication_date": publication_date_iso,
                "summary_text": summary.strip(),
                "raw_data_json": raw_data_json,
                "tags_keywords": list(set(tags))
            }
            
            # TODO: Implement check for existing record before inserting (e.g., by item_url or title+date)

            insert_response = supabase_client.insert_item(**item_data)
            if insert_response:
                logger.info(f"Successfully inserted item for '{org_name}'. URL: {item_data['item_url']}")
                inserted_count += 1
            else:
                logger.error(f"Failed to insert item for '{org_name}'.")

        except Exception as e:
            logger.error(f"Error processing item card #{item_idx+1}: {card.prettify()[:150]}. Error: {e}", exc_info=True)
            skipped_count +=1

    logger.info(f"Finished processing New Jersey Cybersecurity alerts. Total items processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("New Jersey Cybersecurity Data Breach Alert Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_new_jersey_cyber_breaches()
        
    logger.info("New Jersey Cybersecurity Data Breach Alert Scraper Finished")
