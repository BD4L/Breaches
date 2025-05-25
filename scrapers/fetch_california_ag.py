import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
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
SOURCE_ID_CALIFORNIA_AG = 4 # Placeholder for California AG

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://oag.ca.gov/' # Referer can sometimes help
}

def parse_date_flexible(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or date_str.lower() in ['unknown', 'n/a', 'various']:
        return None
    try:
        # dateutil.parser.parse is very flexible
        dt_object = dateutil_parser.parse(date_str)
        return dt_object.isoformat()
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def process_california_ag_breaches():
    """
    Fetches California AG security breach notifications, processes each notification,
    and inserts relevant data into Supabase.
    """
    logger.info("Starting California AG Security Breach Notification processing...")

    try:
        # The CA AG site can be tricky; sometimes it behaves like a Single Page App (SPA) or loads data dynamically.
        # A direct GET request might not always get the full content if JS rendering is heavy.
        # If this consistently fails or returns minimal HTML, a headless browser (Playwright/Selenium) would be needed.
        response = requests.get(CALIFORNIA_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
        logger.info(f"Successfully fetched the page. Status: {response.status_code}. Length: {len(response.text)} bytes.")
        if len(response.text) < 5000: # Arbitrary small length check
             logger.warning("The fetched page content is very short, which might indicate that the main content is loaded via JavaScript.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching California AG breach data page: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # The structure for breach notifications on CA AG site:
    # Typically, data is within a <div> with class 'view-content'.
    # Each breach is often in a <div> with class 'views-row', which then contains a <table> or <dl>.
    # Let's inspect what we get.
    
    # Attempt 1: Common structure seen in the past: div.view-content -> div.views-row -> table
    # As of late 2023/early 2024, it's more like `div.view-content` -> `article.node-breach`
    
    breach_rows_articles = soup.select('article.node-breach') # New structure
    if not breach_rows_articles:
        # Fallback to older structure if the new one isn't found
        breach_rows_divs = soup.select('div.view-content div.views-row') # Older structure
        if not breach_rows_divs:
            logger.error("Could not find breach notification rows using common selectors ('article.node-breach' or 'div.views-row'). The page structure might have changed significantly, or content is JS-loaded.")
            logger.debug(f"Page content sample (first 1000 chars): {response.text[:1000]}")
            return
        else:
            breach_items = breach_rows_divs
            logger.info(f"Found {len(breach_items)} potential breach notifications using 'div.views-row' selector.")
    else:
        breach_items = breach_rows_articles
        logger.info(f"Found {len(breach_items)} potential breach notifications using 'article.node-breach' selector.")


    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    inserted_count = 0
    processed_count = 0
    skipped_count = 0

    for item in breach_items:
        processed_count += 1
        try:
            # Initialize fields
            org_name = None
            date_submitted_str = None
            dates_of_breach_str = None
            num_californians_affected_str = None
            description_of_breach = ""
            pdf_link = None

            # --- Structure for 'article.node-breach' (newer site versions) ---
            if item.name == 'article' and 'node-breach' in item.get('class', []):
                # Organization Name is typically in the title/header of the article
                title_tag = item.find('h2') # Or similar header tag
                if title_tag and title_tag.find('a'):
                    org_name = title_tag.find('a').get_text(strip=True)
                    # The link in the title usually goes to a detailed page for that breach, not the PDF itself.
                    # The PDF link is often found separately.
                elif title_tag:
                     org_name = title_tag.get_text(strip=True)


                # Look for fields within the article body
                # Date Submitted to AG
                date_submitted_label = item.find(lambda tag: tag.name == "div" and "Date Submitted to AG" in tag.get_text() and "field--name-field-sbmt-date" in tag.get('class', []))
                if date_submitted_label and date_submitted_label.find(class_="field--item"):
                    date_submitted_str = date_submitted_label.find(class_="field--item").get_text(strip=True)
                
                # Dates of Breach
                dates_breach_label = item.find(lambda tag: tag.name == "div" and "Date(s) of Breach" in tag.get_text() and "field--name-field-breach-date" in tag.get('class', []))
                if dates_breach_label and dates_breach_label.find(class_="field--item"):
                    dates_of_breach_str = dates_breach_label.find(class_="field--item").get_text(strip=True)

                # Link to Notification (PDF)
                # Often in a field like 'field--name-field-breach-notification'
                pdf_link_tag_container = item.find(class_="field--name-field-breach-notification")
                if pdf_link_tag_container and pdf_link_tag_container.find('a', href=True):
                    pdf_link = urljoin(CALIFORNIA_AG_BREACH_URL, pdf_link_tag_container.find('a')['href'])

                # Description / Type of Information - This can be harder to pinpoint.
                # Might be in a field like 'field--name-field-information-compromised' or general text.
                info_compromised_container = item.find(class_="field--name-field-information-compromised")
                if info_compromised_container and info_compromised_container.find(class_="field--item"):
                    description_of_breach = info_compromised_container.find(class_="field--item").get_text(separator="\n", strip=True)
                
                # Number of Californians Affected - Often NOT on the list page, but in the PDF.
                # Sometimes there's a field 'field--name-field-ca-affected-count'
                affected_count_container = item.find(class_="field--name-field-ca-affected-count")
                if affected_count_container and affected_count_container.find(class_="field--item"):
                    num_californians_affected_str = affected_count_container.find(class_="field--item").get_text(strip=True)


            # --- Fallback structure for 'div.views-row' (older site versions) ---
            elif item.name == 'div' and 'views-row' in item.get('class', []):
                # Organization Name often in a <h4> or <a> tag
                org_name_tag = item.find(['h3', 'h4'])
                if org_name_tag:
                    org_name = org_name_tag.get_text(strip=True)
                
                # Data is often in a <table> or <dl> within the views-row
                table = item.find('table')
                if table:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['th', 'td'])
                        if len(cells) == 2:
                            header = cells[0].get_text(strip=True).lower()
                            value = cells[1].get_text(strip=True)
                            link_tag = cells[1].find('a', href=True)

                            if 'date submitted' in header:
                                date_submitted_str = value
                            elif 'date(s) of breach' in header:
                                dates_of_breach_str = value
                            elif 'notification' in header and link_tag: # Looking for PDF
                                pdf_link = urljoin(CALIFORNIA_AG_BREACH_URL, link_tag['href'])
                            elif 'type of information' in header or 'description' in header:
                                description_of_breach += value + " "
                            elif 'number of californians affected' in header:
                                num_californians_affected_str = value
                else: # Try <dl> definition list if no table
                    dls = item.find_all('dl')
                    for dl_item in dls:
                        dt_tags = dl_item.find_all('dt')
                        dd_tags = dl_item.find_all('dd')
                        for dt, dd in zip(dt_tags, dd_tags):
                            header = dt.get_text(strip=True).lower()
                            value = dd.get_text(strip=True)
                            link_tag = dd.find('a', href=True)

                            if 'date submitted' in header:
                                date_submitted_str = value
                            elif 'date(s) of breach' in header:
                                dates_of_breach_str = value
                            elif 'notification' in header and link_tag:
                                pdf_link = urljoin(CALIFORNIA_AG_BREACH_URL, link_tag['href'])
                            elif 'type of information' in header or 'description' in header:
                                description_of_breach += value + " "
                            elif 'number of californians affected' in header:
                                num_californians_affected_str = value
                
                if not org_name and pdf_link: # Fallback for org name if PDF link has a telling name
                    org_name = os.path.basename(pdf_link).split('.')[0].replace('_', ' ').title()


            if not org_name or not date_submitted_str:
                logger.warning(f"Skipping item due to missing Organization Name or Date Submitted. Data found: Name='{org_name}', DateSub='{date_submitted_str}', PDF='{pdf_link}' Item HTML: {item.prettify()[:300]}")
                skipped_count += 1
                continue

            publication_date_iso = parse_date_flexible(date_submitted_str)
            if not publication_date_iso:
                logger.warning(f"Skipping '{org_name}' due to unparsable submission date: '{date_submitted_str}'")
                skipped_count += 1
                continue

            raw_data = {
                "dates_of_breach": dates_of_breach_str if dates_of_breach_str else "Not specified",
                "californians_affected_on_page": num_californians_affected_str if num_californians_affected_str else "Not specified",
                "pdf_link": pdf_link,
                "date_submitted_original": date_submitted_str, # Store original for reference
                "source_page_html_snippet": item.prettify()[:500] # For debugging structure changes
            }
            raw_data_json = {k: v for k, v in raw_data.items() if v is not None}

            tags = ["california_ag", "ca_breach"]
            # Basic keyword tagging from description (can be expanded)
            if description_of_breach:
                desc_lower = description_of_breach.lower()
                if "email" in desc_lower: tags.append("email_compromised")
                if "ssn" in desc_lower or "social security" in desc_lower : tags.append("ssn_compromised")
                if "payment card" in desc_lower or "credit card" in desc_lower: tags.append("payment_card_compromised")


            item_data = {
                "source_id": SOURCE_ID_CALIFORNIA_AG,
                "item_url": pdf_link if pdf_link else CALIFORNIA_AG_BREACH_URL, # Use PDF link as primary URL
                "title": org_name,
                "publication_date": publication_date_iso,
                "summary_text": description_of_breach.strip() if description_of_breach else "Details in linked PDF.",
                "raw_data_json": raw_data_json,
                "tags_keywords": list(set(tags))
            }

            # TODO: Implement check for existing record before inserting
            # exists = supabase_client.client.table("scraped_items").select("id").eq("item_url", item_data["item_url"]).eq("publication_date", publication_date_iso).execute()
            # if exists.data: continue

            insert_response = supabase_client.insert_item(**item_data)
            if insert_response:
                logger.info(f"Successfully inserted item for '{org_name}'. PDF: {pdf_link}")
                inserted_count += 1
            else:
                logger.error(f"Failed to insert item for '{org_name}'.")

        except Exception as e:
            logger.error(f"Error processing item for '{org_name if org_name else 'Unknown Entity'}': {e}. Item HTML: {item.prettify()[:300]}", exc_info=True)
            skipped_count +=1

    logger.info(f"Finished processing California AG breaches. Total items processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

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
