import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin, unquote
from dateutil import parser as dateutil_parser
import re
import csv
import io

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
PRIVACY_RIGHTS_BASE_URL = "https://privacyrights.org/data-breaches"
SOURCE_ID_PRIVACY_RIGHTS = 30

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def parse_date_flexible_prc(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO 8601 format string or None if parsing fails.
    Handles various date formats found in PRC data.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', 'ongoing', 'see letter', '', '0000-00-00']:
        return None
    try:
        # Handle "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DD"
        if ' ' in date_str: # Contains time component
            dt_object = dateutil_parser.parse(date_str.split(' ')[0])
        else:
            dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def process_privacy_rights_org_data():
    """
    Fetches Privacy Rights Clearinghouse data breach notifications.
    It first attempts to find a CSV download. If not found or fails,
    it falls back to HTML scraping.
    """
    logger.info("Starting Privacy Rights Clearinghouse Data Breach processing...")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    # --- Investigation Step: Attempt CSV Download First ---
    # Privacy Rights Clearinghouse has historically provided a CSV.
    # The direct link used to be something like: https://privacyrights.org/node/6?export=csv
    # Or linked from their data breaches page. Let's try to find such a link.
    
    csv_download_url = None
    try:
        main_page_response = requests.get(PRIVACY_RIGHTS_BASE_URL, headers=REQUEST_HEADERS, timeout=30)
        main_page_response.raise_for_status()
        main_soup = BeautifulSoup(main_page_response.content, 'html.parser')
        
        # Look for links with "csv" in href or text like "Download CSV"
        # Common patterns: <a href="...export=csv"> or <a href="....csv">
        csv_link_tag = main_soup.find('a', href=re.compile(r'export=csv|node/\d+\?export=csv', re.IGNORECASE))
        if not csv_link_tag:
            csv_link_tag = main_soup.find('a', href=re.compile(r'\.csv$', re.IGNORECASE))
        if not csv_link_tag: # Try text search
             csv_link_tag = main_soup.find('a', string=re.compile(r'download csv|export as csv', re.IGNORECASE))

        # Based on past knowledge, a known (but potentially outdated) CSV URL structure exists.
        # Let's try constructing it relative to a base node if the general search fails.
        # The main data view might be on a node like /node/6 or similar.
        # If main_soup.select_one("article[data-history-node-id]"):
        #    node_id = main_soup.select_one("article[data-history-node-id]")['data-history-node-id']
        #    potential_csv_url = f"https://privacyrights.org/node/{node_id}?export=csv"
        #    # We would then check if this URL is valid.
        # For now, the direct CSV link seems to be consistently https://privacyrights.org/data-breach?export=csv
        # As of early 2024, the direct link is https://privacyrights.org/data-breach?export=csv
        # Let's assume this structure or one found by the regex.
        if csv_link_tag:
             csv_download_url = urljoin(PRIVACY_RIGHTS_BASE_URL, csv_link_tag['href'])
        else: # Fallback to the known pattern if no explicit link found
            # Check if current URL already has a view that might support export
            # For PRC, the main /data-breaches page itself is a view.
            # Test if adding ?export=csv works.
            potential_csv_url = PRIVACY_RIGHTS_BASE_URL + "?export=csv"
            try:
                csv_head_response = requests.head(potential_csv_url, headers=REQUEST_HEADERS, timeout=10, allow_redirects=True)
                if csv_head_response.status_code == 200 and 'text/csv' in csv_head_response.headers.get('Content-Type',''):
                    csv_download_url = potential_csv_url
                    logger.info(f"Confirmed potential CSV URL via HEAD request: {csv_download_url}")
                else:
                    logger.info(f"Potential CSV URL {potential_csv_url} does not seem to be a valid CSV download (Status: {csv_head_response.status_code}, Content-Type: {csv_head_response.headers.get('Content-Type','')}).")
            except requests.exceptions.RequestException as e_head:
                 logger.info(f"HEAD request to potential CSV URL {potential_csv_url} failed: {e_head}. Assuming no direct CSV from this pattern.")


        if csv_download_url:
            logger.info(f"Found potential CSV download link: {csv_download_url}")
            try:
                csv_response = requests.get(csv_download_url, headers=REQUEST_HEADERS, timeout=60)
                csv_response.raise_for_status()
                
                # Ensure content type is CSV
                if 'text/csv' not in csv_response.headers.get('Content-Type', '').lower():
                    logger.warning(f"Link {csv_download_url} does not point to a CSV file (Content-Type: {csv_response.headers.get('Content-Type','')}). Attempting to parse anyway if content looks like CSV.")
                    # Could add a check here: if not csv_response.text.startswith("Date Made Public"): raise ValueError("Not CSV")

                csv_content = csv_response.content.decode('utf-8-sig') # utf-8-sig handles BOM
                csvfile = io.StringIO(csv_content)
                reader = csv.DictReader(csvfile)
                
                logger.info("Successfully downloaded and started parsing CSV data from Privacy Rights Clearinghouse.")
                
                inserted_count = 0
                processed_count = 0
                skipped_count = 0

                # CSV Columns (example, verify with actual CSV):
                # "Date Made Public", "Company", "Type of Breach", "Information Compromised", 
                # "Number of Records", "Source URL", "Description of incident", "State"
                
                # PRC CSV has headers like:
                # Date Made Public,Company,City,State,Type of breach,Type of organization,Total Records,Description of incident,Source URL,Date Updated
                # Note: "Total Records" is the field for number affected.

                for row_idx, row in enumerate(reader):
                    processed_count += 1
                    try:
                        org_name = row.get("Company")
                        date_made_public_str = row.get("Date Made Public")
                        
                        if not org_name or not date_made_public_str:
                            logger.warning(f"Skipping CSV row {row_idx+1} due to missing Company or Date Made Public. Row: {row}")
                            skipped_count += 1
                            continue

                        publication_date_iso = parse_date_flexible_prc(date_made_public_str)
                        if not publication_date_iso:
                            # Try "Date Updated" as a fallback if "Date Made Public" is bad
                            date_updated_str = row.get("Date Updated")
                            publication_date_iso = parse_date_flexible_prc(date_updated_str)
                            if not publication_date_iso:
                                logger.warning(f"Skipping CSV row for '{org_name}' due to unparsable dates: Public='{date_made_public_str}', Updated='{date_updated_str}'")
                                skipped_count +=1
                                continue
                            else:
                                logger.info(f"Used 'Date Updated' as publication date for '{org_name}' from CSV.")
                        
                        item_url = row.get("Source URL", "").strip()
                        if not item_url or item_url.lower() == "n/a": # If no source URL, use PRC main page for this item
                            item_url = f"{PRIVACY_RIGHTS_BASE_URL}#item-{row_idx+1}" # Create a pseudo-URL

                        summary = row.get("Description of incident", "").strip()
                        if not summary: # Fallback summary
                            summary = f"Data breach at {org_name}."
                        if row.get("Type of breach"):
                            summary = f"Type: {row.get('Type of breach')}. {summary}"
                        
                        records_affected_str = row.get("Total Records", "").strip() # "Total Records" is their field name
                        # Convert "1,234" to "1234" if needed, or handle "Unknown", "N/A"
                        records_affected_numeric = None
                        if records_affected_str and records_affected_str.lower() not in ['unknown', 'n/a', 'pending', 'undetermined', '']:
                            try: records_affected_numeric = int(records_affected_str.replace(',', ''))
                            except ValueError: 
                                logger.debug(f"Could not parse records_affected_str '{records_affected_str}' to int for '{org_name}'.")


                        raw_data = {
                            "city": row.get("City"),
                            "state": row.get("State"),
                            "type_of_organization": row.get("Type of organization"),
                            "original_total_records_string": records_affected_str,
                            "records_affected_numeric": records_affected_numeric if records_affected_numeric is not None else "Not specified/Unknown",
                            "type_of_breach_csv": row.get("Type of breach"),
                            "date_updated_csv": row.get("Date Updated"),
                            # Add other relevant CSV fields if needed
                        }
                        raw_data_json = {k: v for k, v in raw_data.items() if v is not None and str(v).strip() != ""}

                        tags = ["privacy_rights", "data_breach"]
                        if raw_data.get("type_of_breach_csv"):
                            tags.append(raw_data["type_of_breach_csv"].lower().replace(" ", "_").replace("/", "_"))
                        if raw_data.get("type_of_organization"):
                            tags.append(raw_data["type_of_organization"].lower().replace(" ", "_"))
                        if records_affected_numeric is not None:
                            if records_affected_numeric >= 1_000_000: tags.append("large_scale_breach")
                            elif records_affected_numeric >= 100_000: tags.append("medium_scale_breach")
                        
                        item_data = {
                            "source_id": SOURCE_ID_PRIVACY_RIGHTS,
                            "item_url": item_url,
                            "title": org_name,
                            "publication_date": publication_date_iso,
                            "summary_text": summary,
                            "raw_data_json": raw_data_json,
                            "tags_keywords": list(set(tags))
                        }
                        
                        insert_response = supabase_client.insert_item(**item_data)
                        if insert_response:
                            inserted_count += 1
                        else:
                            logger.error(f"Failed to insert CSV item for '{org_name}'.")

                    except Exception as e_row:
                        logger.error(f"Error processing CSV row {row_idx+1} for '{org_name if 'org_name' in locals() else 'Unknown Entity'}': {e_row}", exc_info=True)
                        skipped_count +=1
                
                logger.info(f"Finished processing CSV data from Privacy Rights Clearinghouse. Total rows: {processed_count}. Inserted: {inserted_count}. Skipped: {skipped_count}")
                return # Successfully processed CSV, so exit function

            except Exception as e_csv:
                logger.error(f"Failed to download or process CSV from {csv_download_url}: {e_csv}", exc_info=True)
                logger.info("CSV download/processing failed. Falling back to HTML scraping if possible.")
        else:
            logger.info("No direct CSV download link found or confirmed. Proceeding to HTML scraping attempt.")

    except requests.exceptions.RequestException as e_main_page:
        logger.error(f"Error fetching main page {PRIVACY_RIGHTS_BASE_URL} for CSV link discovery: {e_main_page}")
        logger.info("Cannot check for CSV. Attempting HTML scraping directly.")
    except Exception as e_initial: # Catch any other error during CSV phase
        logger.error(f"An unexpected error occurred during CSV processing attempt: {e_initial}", exc_info=True)
        logger.info("Falling back to HTML scraping due to unexpected error during CSV phase.")


    # --- HTML Scraping (If CSV Download is Not Feasible or Failed) ---
    logger.info("Attempting HTML scraping for Privacy Rights Clearinghouse...")
    
    # The PRC website lists breaches typically in a table or structured list.
    # As of early 2024, it's a table with class "table views-view-table".
    # Pagination is present.
    
    current_page_url = PRIVACY_RIGHTS_BASE_URL
    page_num = 0
    
    inserted_count_html = 0
    processed_count_html = 0
    skipped_count_html = 0

    while current_page_url:
        logger.info(f"Fetching HTML page: {current_page_url} (Page approx. {page_num})")
        try:
            response = requests.get(current_page_url, headers=REQUEST_HEADERS, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching HTML page {current_page_url}: {e}")
            break # Stop if a page fails to load

        data_table = soup.find('table', class_="views-view-table") # Specific class used by PRC
        if not data_table:
            # Fallback if specific class not found
            data_table = soup.find('table', class_=re.compile(r'table'))
            if not data_table:
                logger.error(f"No data table (e.g., class 'views-view-table' or generic 'table') found on page {current_page_url}. HTML structure may have changed. Aborting HTML scrape.")
                if page_num == 0: # If this is the first page, it's a critical failure for HTML method
                    logger.error("Could not find data table on the first page. Scraper cannot proceed.")
                    # Consider reporting unfeasible here if CSV also failed.
                break 
        
        tbody = data_table.find('tbody')
        rows = tbody.find_all('tr') if tbody else data_table.find_all('tr')[1:] # Skip header if no tbody

        if not rows:
            logger.info(f"No breach rows found in table on page {current_page_url}.")
            break # No more data

        # Column mapping from HTML table (inspect page to confirm):
        # 0: Date Made Public
        # 1: Company, City, State (often combined or Company is a link)
        # 2: Type of Breach
        # 3: Type of Organization (optional, might not always be there)
        # 4: Total Records (optional)
        # Link to details might be on Company name or a separate column (not usually on PRC list)

        for row_idx, row in enumerate(rows):
            processed_count_html += 1
            cols = row.find_all('td')

            if len(cols) < 2: # Need at least Date and Company info
                logger.warning(f"Skipping HTML row {row_idx+1} on {current_page_url} due to insufficient columns ({len(cols)}).")
                skipped_count_html += 1
                continue
            
            try:
                date_made_public_str = cols[0].get_text(strip=True)
                
                company_cell = cols[1]
                org_name = company_cell.get_text(strip=True) # Full text of cell
                # Extract city/state if present and clean org_name
                # Example: "Org Inc, Anytown, CA" -> Org Name: "Org Inc", City: "Anytown", State: "CA"
                city_state_match = re.search(r',\s*([^,]+),\s*([A-Z]{2})$', org_name)
                city = None
                state = None
                if city_state_match:
                    org_name = org_name[:city_state_match.start()].strip()
                    city = city_state_match.group(1).strip()
                    state = city_state_match.group(2).strip()
                
                # Link might be on org_name
                item_specific_url = None
                link_tag_in_company = company_cell.find('a', href=True)
                if link_tag_in_company:
                    item_specific_url = urljoin(PRIVACY_RIGHTS_BASE_URL, link_tag_in_company['href'])
                    # If the link text is the same as the cleaned org_name, it's fine.
                    # If link text is different, org_name might need to be link_tag_in_company.get_text(strip=True)
                    # For PRC, typically the full cell text is the org name, and part of it is linked.

                type_of_breach = cols[2].get_text(strip=True) if len(cols) > 2 else "Not specified"
                type_of_org = cols[3].get_text(strip=True) if len(cols) > 3 else "Not specified"
                records_affected_str = cols[4].get_text(strip=True) if len(cols) > 4 else "Not specified"


                if not org_name or not date_made_public_str:
                    logger.warning(f"Skipping HTML row on {current_page_url} due to missing Org Name or Date. Name: '{org_name}', Date: '{date_made_public_str}'")
                    skipped_count_html += 1
                    continue

                publication_date_iso = parse_date_flexible_prc(date_made_public_str)
                if not publication_date_iso:
                    logger.warning(f"Skipping HTML row for '{org_name}' on {current_page_url} due to unparsable date: '{date_made_public_str}'")
                    skipped_count_html += 1
                    continue

                summary = f"Type: {type_of_breach}."
                if type_of_org and type_of_org.lower() != 'not specified': summary += f" Org Type: {type_of_org}."
                if records_affected_str and records_affected_str.lower() not in ['not specified', 'unknown', 'pending', 'n/a']:
                    summary += f" Records Affected: {records_affected_str}."
                
                records_affected_numeric_html = None
                if records_affected_str and records_affected_str.lower() not in ['unknown', 'n/a', 'pending', 'undetermined', '']:
                    try: records_affected_numeric_html = int(records_affected_str.replace(',', ''))
                    except ValueError: 
                        logger.debug(f"Could not parse records_affected_str '{records_affected_str}' from HTML to int for '{org_name}'.")


                raw_data_html = {
                    "city_from_html": city,
                    "state_from_html": state,
                    "type_of_organization_html": type_of_org,
                    "original_records_affected_string_html": records_affected_str,
                    "records_affected_numeric_html": records_affected_numeric_html if records_affected_numeric_html is not None else "Not specified/Unknown",
                    "type_of_breach_html": type_of_breach,
                    "source_page_num_approx": page_num
                }
                raw_data_json_html = {k: v for k, v in raw_data_html.items() if v is not None and str(v).strip() != ""}


                tags_html = ["privacy_rights", "data_breach", "html_scrape"]
                if type_of_breach and type_of_breach.lower() != 'not specified':
                    tags_html.append(type_of_breach.lower().replace(" ", "_").replace("/", "_"))
                if type_of_org and type_of_org.lower() != 'not specified':
                    tags_html.append(type_of_org.lower().replace(" ", "_"))
                if records_affected_numeric_html is not None:
                    if records_affected_numeric_html >= 1_000_000: tags_html.append("large_scale_breach")
                    elif records_affected_numeric_html >= 100_000: tags_html.append("medium_scale_breach")


                item_data_html = {
                    "source_id": SOURCE_ID_PRIVACY_RIGHTS,
                    "item_url": item_specific_url if item_specific_url else f"{PRIVACY_RIGHTS_BASE_URL}#page-{page_num}-item-{row_idx}",
                    "title": org_name,
                    "publication_date": publication_date_iso,
                    "summary_text": summary.strip(),
                    "raw_data_json": raw_data_json_html,
                    "tags_keywords": list(set(tags_html))
                }
                
                insert_response_html = supabase_client.insert_item(**item_data_html)
                if insert_response_html:
                    inserted_count_html += 1
                else:
                    logger.error(f"Failed to insert HTML item for '{org_name}' from {current_page_url}.")

            except Exception as e_row_html:
                logger.error(f"Error processing HTML row for '{org_name if 'org_name' in locals() else 'Unknown Entity'}' on {current_page_url}: {e_row_html}", exc_info=True)
                skipped_count_html +=1
        
        # Pagination for HTML scraping
        # PRC uses Drupal-style pagers: <li class="pager__item pager__item--next"><a href="?page=1">
        next_page_tag = soup.select_one("li.pager__item--next a[href], li.pager-next a[href]") # Common pager classes
        if next_page_tag and next_page_tag.has_attr('href'):
            current_page_url = urljoin(PRIVACY_RIGHTS_BASE_URL, next_page_tag['href'])
            page_num += 1
            if PRIVACY_RIGHTS_BASE_URL in current_page_url and f"page={page_num-2}" in current_page_url and page_num > 50: # Safety break for excessive paging or loop
                 logger.warning(f"Potential pagination loop or excessive pages. Stopping at page {page_num}. URL: {current_page_url}")
                 break
        else:
            current_page_url = None # No more next page

    if processed_count_html > 0: # Log summary if HTML scraping was attempted
        logger.info(f"Finished HTML scraping for Privacy Rights Clearinghouse. Total HTML items processed: {processed_count_html}. Inserted: {inserted_count_html}. Skipped: {skipped_count_html}")
    elif page_num == 0 and not csv_download_url : # If first page HTML scrape failed AND CSV wasn't found
        logger.error("Both CSV and HTML scraping methods failed to yield data for Privacy Rights Clearinghouse. The site structure might be too complex for current tools or requires JavaScript rendering.")
        # This is where you'd report "unfeasible" if no data could be obtained by either method.

if __name__ == "__main__":
    logger.info("Privacy Rights Clearinghouse Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_privacy_rights_org_data()
        
    logger.info("Privacy Rights Clearinghouse Scraper Finished")
