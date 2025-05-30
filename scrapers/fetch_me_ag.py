import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from urllib.parse import urljoin
from dateutil import parser as dateutil_parser
import hashlib
import re
import io
import time

# Assuming SupabaseClient is in utils.supabase_client
try:
    from utils.supabase_client import SupabaseClient, clean_text_for_database
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from utils.supabase_client import SupabaseClient, clean_text_for_database

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
MAINE_AG_LIST_URL = "https://www.maine.gov/agviewer/content/ag/985235c7-cb95-4be2-8792-a1252b4f8318/list.html"
SOURCE_ID_MAINE_AG = 9

# Configuration from environment variables
FILTER_FROM_DATE = os.environ.get("ME_AG_FILTER_FROM_DATE", "2025-01-20")  # Default: 2025 breaches only
PROCESSING_MODE = os.environ.get("ME_AG_PROCESSING_MODE", "ENHANCED")  # BASIC, ENHANCED, FULL
MAX_PAGES = int(os.environ.get("ME_AG_MAX_PAGES", "5"))  # Limit pages to process

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Rate limiting
RATE_LIMIT_DELAY = 2  # seconds between requests

def rate_limit_delay():
    """Add delay between requests to be respectful to the server."""
    time.sleep(RATE_LIMIT_DELAY)

def parse_date_flexible_me(date_str: str) -> str | None:
    """
    Parse Maine AG date strings (format: YYYY-MM-DD) to ISO 8601 format.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', 'ongoing']:
        return None
    try:
        # Maine AG uses YYYY-MM-DD format (e.g., "2025-05-27")
        dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse Maine AG date string: '{date_str}'. Error: {e}")
        return None

def parse_date_to_date_only(date_str: str) -> str | None:
    """
    Parse date string and return only the date part (YYYY-MM-DD).
    """
    if not date_str:
        return None
    try:
        dt_object = dateutil_parser.parse(date_str.strip())
        return dt_object.date().isoformat()
    except (ValueError, TypeError, OverflowError):
        return None

def generate_incident_uid_me(organization_name: str, reported_date: str) -> str:
    """
    Generate a unique incident identifier for Maine AG breaches.
    Format: ME_AG_{hash}
    """
    # Create a unique string from organization name and date
    unique_string = f"maine_ag_{organization_name.lower().strip()}_{reported_date}"
    # Generate a short hash
    hash_object = hashlib.md5(unique_string.encode())
    short_hash = hash_object.hexdigest()[:8]
    return f"ME_AG_{short_hash.upper()}"

def should_process_record_me(reported_date_str: str) -> bool:
    """
    Determine if a breach record should be processed based on date filtering.
    """
    if not FILTER_FROM_DATE:
        return True

    try:
        filter_date = datetime.strptime(FILTER_FROM_DATE, "%Y-%m-%d").date()

        # Parse the reported date
        parsed_date = parse_date_to_date_only(reported_date_str)
        if parsed_date:
            record_date = datetime.strptime(parsed_date, "%Y-%m-%d").date()
            return record_date >= filter_date

        # If no valid date found, include the record
        return True

    except Exception as e:
        logger.warning(f"Error in date filtering: {e}")
        return True

def extract_affected_individuals_me(text: str) -> int | None:
    """
    Extract number of affected individuals from text using regex patterns.
    For Maine AG, handles both descriptive text and raw numbers.
    """
    if not text:
        return None

    # First try to extract just numbers (for Maine AG raw values like "364,333" or "67947")
    number_only_pattern = r'^(\d{1,3}(?:,\d{3})*|\d+)$'
    number_match = re.match(number_only_pattern, text.strip())
    if number_match:
        try:
            number_str = number_match.group(1).replace(',', '')
            return int(number_str)
        except (ValueError, IndexError):
            pass

    # Common patterns for affected individuals in descriptive text
    patterns = [
        r'(\d{1,3}(?:,\d{3})*)\s*(?:individuals?|people|persons?|residents?|customers?|patients?|members?)',
        r'(?:affecting|affected|impacted)\s*(\d{1,3}(?:,\d{3})*)',
        r'(\d{1,3}(?:,\d{3})*)\s*(?:maine\s*)?(?:residents?|individuals?)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text.lower())
        if matches:
            try:
                # Remove commas and convert to int
                number_str = matches[0].replace(',', '')
                return int(number_str)
            except (ValueError, IndexError):
                continue

    return None

def analyze_pdf_content_me(pdf_url: str) -> dict:
    """
    Enhanced PDF content analysis for comprehensive breach details (Tier 3).
    Extracts affected individuals, data types, and incident details from Maine AG PDFs.
    """
    try:
        logger.info(f"Analyzing Maine AG PDF: {pdf_url}")

        pdf_analysis = {
            'pdf_analyzed': True,
            'pdf_url': pdf_url,
            'affected_individuals': None,
            'what_information_involved': {},
            'raw_text': '',
            'extraction_confidence': 'low'  # Track confidence in extraction
        }

        # Add rate limiting delay before PDF request
        rate_limit_delay()

        # Extract PDF content using local libraries (PyPDF2 and pdfplumber)
        try:
            response = requests.get(pdf_url, headers=REQUEST_HEADERS, timeout=30)
            response.raise_for_status()

            if response.status_code == 200:
                # Try PyPDF2 first
                try:
                    import PyPDF2
                    pdf_file = io.BytesIO(response.content)
                    pdf_reader = PyPDF2.PdfReader(pdf_file)

                    text_content = ""
                    for page in pdf_reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_content += page_text + "\n"

                    if text_content.strip():
                        # Clean the extracted text to prevent Unicode errors in database
                        text_content = clean_text_for_database(text_content)
                        content = text_content.lower()
                        pdf_analysis['raw_text'] = text_content[:1000]  # Store sample
                        pdf_analysis['extraction_confidence'] = 'high'
                        logger.debug(f"PyPDF2 extraction successful for {pdf_url}")
                    else:
                        raise Exception("No text extracted from PDF with PyPDF2")

                except ImportError:
                    logger.debug("PyPDF2 not available, trying pdfplumber")
                    raise Exception("PyPDF2 not available")

                except Exception as pypdf_error:
                    logger.debug(f"PyPDF2 extraction failed: {pypdf_error}, trying pdfplumber")

                    # Try pdfplumber as alternative
                    try:
                        import pdfplumber
                        pdf_file = io.BytesIO(response.content)

                        text_content = ""
                        with pdfplumber.open(pdf_file) as pdf:
                            for page in pdf.pages:
                                page_text = page.extract_text()
                                if page_text:
                                    text_content += page_text + "\n"

                        if text_content.strip():
                            # Clean the extracted text to prevent Unicode errors in database
                            text_content = clean_text_for_database(text_content)
                            content = text_content.lower()
                            pdf_analysis['raw_text'] = text_content[:1000]  # Store sample
                            pdf_analysis['extraction_confidence'] = 'high'
                            logger.debug(f"pdfplumber extraction successful for {pdf_url}")
                        else:
                            raise Exception("No text extracted from PDF with pdfplumber")

                    except ImportError:
                        logger.warning("Neither PyPDF2 nor pdfplumber available for PDF extraction")
                        pdf_analysis['extraction_confidence'] = 'failed'
                        return pdf_analysis

                    except Exception as pdfplumber_error:
                        logger.warning(f"Both PyPDF2 and pdfplumber failed for {pdf_url}: {pdfplumber_error}")
                        pdf_analysis['extraction_confidence'] = 'failed'
                        return pdf_analysis

                # Extract affected individuals
                affected_individuals = extract_affected_individuals_me(text_content)
                if affected_individuals:
                    pdf_analysis['affected_individuals'] = affected_individuals

                # Extract "what information was involved" section
                what_info_patterns = [
                    r'what\s+(?:information|data)\s+(?:was\s+)?(?:involved|affected|compromised|accessed|disclosed)',
                    r'types?\s+of\s+(?:information|data)\s+(?:involved|affected|compromised)',
                    r'personal\s+information\s+(?:involved|affected|compromised)',
                    r'information\s+(?:that\s+)?(?:may\s+have\s+been\s+)?(?:involved|affected|compromised|accessed)'
                ]

                for pattern in what_info_patterns:
                    match = re.search(pattern, content)
                    if match:
                        # Extract text after the pattern (next 500 characters)
                        start_pos = match.end()
                        extracted_text = text_content[start_pos:start_pos + 500].strip()
                        if extracted_text:
                            pdf_analysis['what_information_involved']['text'] = extracted_text
                            break

                logger.info(f"Successfully analyzed PDF: {pdf_url}")

        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to download PDF {pdf_url}: {e}")
            pdf_analysis['extraction_confidence'] = 'failed'

        except Exception as e:
            logger.warning(f"Error analyzing PDF {pdf_url}: {e}")
            pdf_analysis['extraction_confidence'] = 'failed'

        return pdf_analysis

    except Exception as e:
        logger.error(f"Critical error in PDF analysis for {pdf_url}: {e}")
        return {
            'pdf_analyzed': False,
            'pdf_url': pdf_url,
            'error': str(e),
            'extraction_confidence': 'failed'
        }

def extract_breach_details_from_page(page_data: dict) -> dict:
    """
    Extract specific breach details from the parsed page data.
    Returns structured breach information.
    """
    breach_details = {
        'total_affected': None,
        'maine_residents_affected': None,
        'breach_occurred_date': None,
        'breach_discovered_date': None,
        'breach_description': None,
        'information_acquired': None,
        'consumer_agencies_notified': None
    }

    if not page_data.get('extraction_success'):
        return breach_details

    breach_info = page_data.get('breach_info', {})

    # Extract total affected individuals
    for key, value in breach_info.items():
        key_lower = key.lower().replace('_', ' ').replace('-', ' ')

        if 'total number of persons affected' in key_lower and 'including residents' in key_lower:
            affected_num = extract_affected_individuals_me(value)
            if affected_num:
                breach_details['total_affected'] = affected_num

        elif 'total number of maine residents affected' in key_lower:
            maine_affected = extract_affected_individuals_me(value)
            if maine_affected:
                breach_details['maine_residents_affected'] = maine_affected

        elif 'date(s) breach occured' in key_lower or 'date breach occurred' in key_lower:
            breach_date = parse_date_flexible_me(value)
            if breach_date:
                breach_details['breach_occurred_date'] = breach_date

        elif 'date breach discovered' in key_lower:
            discovery_date = parse_date_flexible_me(value)
            if discovery_date:
                breach_details['breach_discovered_date'] = discovery_date

        elif 'description of the breach' in key_lower:
            breach_details['breach_description'] = value

        elif 'information acquired' in key_lower and 'name or other personal identifier' in key_lower:
            # This is the detailed information about what was compromised
            breach_details['information_acquired'] = value

        elif 'consumer reporting agencies been notified' in key_lower:
            breach_details['consumer_agencies_notified'] = value

    return breach_details

def process_individual_breach_page(page_url: str) -> dict:
    """
    Process an individual Maine AG breach notification page to extract detailed information.
    Returns structured data from the page.
    """
    try:
        logger.info(f"Processing individual breach page: {page_url}")

        # Add rate limiting delay
        rate_limit_delay()

        response = requests.get(page_url, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Initialize data structure
        page_data = {
            'page_url': page_url,
            'entity_info': {},
            'submitted_by': {},
            'breach_info': {},
            'notification_services': {},
            'extraction_success': True
        }

        # Extract Entity Information
        entity_section = soup.find('h2', string='Entity Information')
        if entity_section:
            entity_list = entity_section.find_next_sibling('ul')
            if entity_list:
                for li in entity_list.find_all('li'):
                    text = li.get_text(strip=True)
                    if ':' in text:
                        key, value = text.split(':', 1)
                        key = key.strip().lower().replace(' ', '_')
                        value = value.strip('* ')
                        page_data['entity_info'][key] = value

        # Extract Submitted By Information
        submitted_section = soup.find('h2', string='Submitted By')
        if submitted_section:
            submitted_list = submitted_section.find_next_sibling('ul')
            if submitted_list:
                for li in submitted_list.find_all('li'):
                    text = li.get_text(strip=True)
                    if ':' in text:
                        key, value = text.split(':', 1)
                        key = key.strip().lower().replace(' ', '_')
                        value = value.strip('* ')
                        page_data['submitted_by'][key] = value

        # Extract Breach Information (Enhanced)
        breach_section = soup.find('h2', string='Breach Information')
        if breach_section:
            breach_list = breach_section.find_next_sibling('ul')
            if breach_list:
                for li in breach_list.find_all('li'):
                    text = li.get_text(strip=True)
                    if ':' in text:
                        key, value = text.split(':', 1)
                        key = key.strip().lower().replace(' ', '_')
                        value = value.strip('* ')
                        page_data['breach_info'][key] = value

        # Extract Notification and Protection Services
        notification_section = soup.find('h2', string='Notification and Protection Services')
        if notification_section:
            notification_list = notification_section.find_next_sibling('ul')
            if notification_list:
                for li in notification_list.find_all('li'):
                    text = li.get_text(strip=True)
                    if ':' in text:
                        key, value = text.split(':', 1)
                        key = key.strip().lower().replace(' ', '_')
                        value = value.strip('* ')
                        page_data['notification_services'][key] = value

                    # Extract PDF link if present
                    pdf_link = li.find('a', href=True)
                    if pdf_link:
                        pdf_href = pdf_link['href']
                        if 'pdf' in pdf_href.lower() or 'pdf' in pdf_link.get_text().lower():
                            # Convert relative URL to absolute URL
                            pdf_url = urljoin(page_url, pdf_href)
                            page_data['notification_services']['pdf_url'] = pdf_url
                            logger.info(f"Found PDF URL: {pdf_url}")

                    # Also check if the text itself contains a PDF filename
                    elif ':' in text and 'pdf' in text.lower():
                        key, value = text.split(':', 1)
                        value = value.strip('* ')
                        if value and 'pdf' in value.lower():
                            # Construct PDF URL from filename
                            pdf_url = urljoin(page_url, value)
                            page_data['notification_services']['pdf_url'] = pdf_url
                            logger.info(f"Constructed PDF URL from filename: {pdf_url}")

        logger.info(f"Successfully extracted data from breach page: {page_url}")
        return page_data

    except Exception as e:
        logger.error(f"Error processing individual breach page {page_url}: {e}")
        return {
            'page_url': page_url,
            'extraction_success': False,
            'error': str(e)
        }

def process_maine_ag_breaches_enhanced():
    """
    Enhanced Maine AG Security Breach Notification processing with 3-tier data structure.
    Processes the list page and follows links to individual breach notification pages.
    """
    logger.info("Starting Enhanced Maine AG Security Breach Notification processing...")

    # Filter configuration
    if FILTER_FROM_DATE:
        try:
            filter_date = datetime.strptime(FILTER_FROM_DATE, '%Y-%m-%d').date()
            logger.info(f"Date filtering enabled: collecting breaches from {filter_date} onward")
        except ValueError:
            logger.warning(f"Invalid FILTER_FROM_DATE format '{FILTER_FROM_DATE}', using one week back")
            filter_date = (date.today() - timedelta(days=7))
    else:
        filter_date = None
        logger.info("Testing mode: collecting ALL Maine AG breach data (no date filtering)")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    inserted_count = 0
    processed_count = 0
    skipped_count = 0

    # Process multiple pages of the list
    for page_num in range(1, MAX_PAGES + 1):
        logger.info(f"Processing Maine AG list page {page_num}/{MAX_PAGES}")

        # Construct page URL (page 1 is the base URL, others have ?page=N)
        if page_num == 1:
            page_url = MAINE_AG_LIST_URL
        else:
            page_url = f"{MAINE_AG_LIST_URL}?page={page_num}"

        try:
            response = requests.get(page_url, headers=REQUEST_HEADERS, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Maine AG list page {page_num}: {e}")
            continue

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the table containing breach notifications
        table = soup.find('table')
        if not table:
            logger.error(f"Could not find table on page {page_num}. Page structure might have changed.")
            continue

        # Extract table rows (skip header row)
        tbody = table.find('tbody')
        if not tbody:
            table_rows = table.find_all('tr')
            # Remove header row if present (first <tr> with <th>)
            if table_rows and table_rows[0].find_all('th'):
                table_rows = table_rows[1:]
        else:
            table_rows = tbody.find_all('tr')

        if not table_rows:
            logger.info(f"No breach notification rows found on page {page_num}.")
            continue

        logger.info(f"Found {len(table_rows)} potential breach notifications on page {page_num}.")

        # Process each table row
        for row_idx, row in enumerate(table_rows):
            processed_count += 1
            cols = row.find_all('td')

            if len(cols) < 2:  # Need at least Date Reported and Organization Name
                logger.warning(f"Skipping row {row_idx+1} on page {page_num} due to insufficient columns ({len(cols)})")
                skipped_count += 1
                continue

            try:
                # Extract basic data from table columns
                # Column 0: Date Reported
                # Column 1: Organization Name (with link to individual page)
                date_reported_str = cols[0].get_text(strip=True)
                organization_cell = cols[1]  # Cell contains organization name and link

                # Extract organization name and link
                organization_name = organization_cell.get_text(strip=True)
                link_tag = organization_cell.find('a', href=True)

                if not link_tag:
                    logger.warning(f"No link found for '{organization_name}' on page {page_num}. Skipping.")
                    skipped_count += 1
                    continue

                # Construct full URL to individual breach page
                individual_page_url = urljoin(MAINE_AG_LIST_URL, link_tag['href'])

                # Skip if we don't have essential data
                if not organization_name or not date_reported_str or not individual_page_url:
                    logger.warning(f"Skipping row {row_idx+1} on page {page_num} due to missing essential data")
                    skipped_count += 1
                    continue

                # Apply date filtering
                if not should_process_record_me(date_reported_str):
                    logger.info(f"Skipping '{organization_name}' - reported date {date_reported_str} is before filter date")
                    skipped_count += 1
                    continue

                # Parse dates
                publication_date_iso = parse_date_flexible_me(date_reported_str)
                if not publication_date_iso:
                    logger.warning(f"Skipping '{organization_name}' due to unparsable reported date: '{date_reported_str}'")
                    skipped_count += 1
                    continue

                reported_date_only = parse_date_to_date_only(date_reported_str)

                # Generate incident UID for deduplication
                incident_uid = generate_incident_uid_me(organization_name, reported_date_only or date_reported_str)

                # Check if item already exists
                unique_url = f"{individual_page_url}#{incident_uid}"
                if supabase_client.check_item_exists(unique_url):
                    logger.info(f"Item already exists for '{organization_name}' on {date_reported_str}. Skipping.")
                    skipped_count += 1
                    continue

                # Build 3-tier data structure
                raw_data = {
                    # Tier 1: Portal Data (Raw extraction from list table)
                    "tier_1_portal_data": {
                        "source_url": page_url,
                        "extraction_timestamp": datetime.now().isoformat(),
                        "page_number": page_num,
                        "table_row_index": row_idx,
                        "raw_date_reported": date_reported_str,
                        "raw_organization_name": organization_name,
                        "individual_page_url": individual_page_url,
                        "processing_mode": PROCESSING_MODE
                    },

                    # Tier 2: Derived/enrichment (computed fields)
                    "tier_2_enhanced": {
                        "incident_uid": incident_uid,
                        "portal_first_seen_utc": datetime.now().isoformat(),
                        "portal_last_seen_utc": datetime.now().isoformat(),
                        "individual_page_processed": False,
                        "enhancement_attempted": False,
                        "enhancement_errors": []
                    },

                    # Tier 3: Deep-dive from individual page (placeholder)
                    "tier_3_individual_page": {}
                }

                # Initialize variables for enhanced data
                affected_individuals = None
                what_was_leaked_value = None
                breach_occurred_date = None
                pdf_url = None

                # Process individual breach page based on processing mode
                if PROCESSING_MODE in ["ENHANCED", "FULL"]:
                    try:
                        individual_page_data = process_individual_breach_page(individual_page_url)
                        raw_data["tier_3_individual_page"] = individual_page_data
                        raw_data["tier_2_enhanced"]["individual_page_processed"] = True
                        raw_data["tier_2_enhanced"]["enhancement_attempted"] = True

                        # Extract enhanced data from individual page
                        if individual_page_data.get('extraction_success'):
                            # Extract structured breach details
                            breach_details = extract_breach_details_from_page(individual_page_data)

                            # Use total affected (prioritize over Maine residents)
                            affected_individuals = breach_details.get('total_affected') or breach_details.get('maine_residents_affected')

                            # Extract breach occurred date
                            if breach_details.get('breach_occurred_date'):
                                breach_occurred_date = parse_date_to_date_only(breach_details['breach_occurred_date'])

                            # Build comprehensive "what was leaked" information
                            leaked_info_parts = []
                            if breach_details.get('breach_description'):
                                leaked_info_parts.append(f"Breach Type: {breach_details['breach_description']}")
                            if breach_details.get('information_acquired'):
                                # This is the key field - what data was actually compromised
                                leaked_info_parts.append(f"Information Acquired - Name or other personal identifier in combination with: {breach_details['information_acquired']}")
                            if breach_details.get('consumer_agencies_notified'):
                                leaked_info_parts.append(f"Consumer Agencies Notified: {breach_details['consumer_agencies_notified']}")

                            if leaked_info_parts:
                                what_was_leaked_value = " | ".join(leaked_info_parts)[:1000]  # Increased limit for detailed info

                            # Store breach details in raw data
                            raw_data["tier_3_individual_page"]["breach_details"] = breach_details

                            # Extract PDF URL from notification services
                            pdf_url = individual_page_data.get('notification_services', {}).get('pdf_url')
                            if pdf_url and PROCESSING_MODE == "FULL":
                                try:
                                    pdf_analysis = analyze_pdf_content_me(pdf_url)
                                    raw_data["tier_3_individual_page"]["pdf_analysis"] = pdf_analysis

                                    # Extract additional data from PDF if available
                                    if pdf_analysis.get('affected_individuals'):
                                        affected_individuals = pdf_analysis['affected_individuals']

                                    if pdf_analysis.get('what_information_involved', {}).get('text'):
                                        what_was_leaked_value = pdf_analysis['what_information_involved']['text']

                                except Exception as e:
                                    logger.warning(f"PDF analysis failed for '{organization_name}': {e}")
                                    raw_data["tier_2_enhanced"]["enhancement_errors"].append(f"PDF analysis failed: {str(e)}")

                    except Exception as e:
                        logger.warning(f"Individual page processing failed for '{organization_name}': {e}")
                        raw_data["tier_2_enhanced"]["enhancement_errors"].append(f"Individual page processing failed: {str(e)}")
                        what_was_leaked_value = individual_page_url  # Fallback to page URL
                else:
                    # In BASIC mode, just use page URL as fallback
                    what_was_leaked_value = individual_page_url

                # Build summary
                summary = f"Security breach notification for {organization_name} reported to Maine AG on {date_reported_str}."

                # Build full content
                full_content = f"Organization: {organization_name}\n"
                full_content += f"Date Reported to Maine AG: {date_reported_str}\n"
                full_content += f"Individual Page: {individual_page_url}\n"

                # Prepare database item
                db_item = {
                    'source_id': SOURCE_ID_MAINE_AG,
                    'item_url': unique_url,
                    'title': organization_name,
                    'publication_date': publication_date_iso,
                    'summary_text': summary,
                    'full_content': full_content,
                    'reported_date': reported_date_only,
                    'breach_date': breach_occurred_date,  # When the breach actually occurred
                    'affected_individuals': affected_individuals,
                    'notice_document_url': pdf_url or individual_page_url,  # PDF URL if available, otherwise page URL
                    'what_was_leaked': what_was_leaked_value,
                    'tags_keywords': ["maine_ag", "me_breach", f"page_{page_num}"],
                    'raw_data_json': {
                        'scraper_version': '1.0_enhanced_maine_ag',
                        **raw_data
                    }
                }

                # Insert into database
                insert_response = supabase_client.insert_item(**db_item)
                if insert_response:
                    logger.info(f"Successfully inserted item for '{organization_name}' reported on {date_reported_str}. URL: {unique_url}")
                    inserted_count += 1
                else:
                    logger.error(f"Failed to insert item for '{organization_name}' reported on {date_reported_str}")

            except Exception as e:
                logger.error(f"Error processing row for '{organization_name if 'organization_name' in locals() else 'Unknown Organization'}': {row.text[:150]}. Error: {e}", exc_info=True)
                skipped_count += 1

    logger.info(f"Finished processing Maine AG breaches. Total items processed: {processed_count}. Items inserted: {inserted_count}. Items skipped: {skipped_count}")

if __name__ == "__main__":
    logger.info("Enhanced Maine AG Security Breach Scraper Started")

    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        logger.info(f"Processing mode: {PROCESSING_MODE}")
        logger.info(f"Max pages to process: {MAX_PAGES}")
        if FILTER_FROM_DATE:
            logger.info(f"Date filtering enabled from: {FILTER_FROM_DATE}")
        else:
            logger.info("Date filtering disabled - collecting all Maine AG data")

        process_maine_ag_breaches_enhanced()

    logger.info("Enhanced Maine AG Security Breach Scraper Finished")
