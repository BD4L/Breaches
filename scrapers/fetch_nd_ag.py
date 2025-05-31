import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urljoin
from dateutil import parser as dateutil_parser
import re
import hashlib
import time
import random

# Selenium imports for JavaScript-rendered content
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# Setup basic logging first
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# PDF processing imports
try:
    import pdfplumber
    import PyPDF2
    PDF_PROCESSING_AVAILABLE = True
except ImportError:
    PDF_PROCESSING_AVAILABLE = False
    logger.warning("PDF processing libraries not available. Install pdfplumber and PyPDF2 for enhanced functionality.")

# Assuming SupabaseClient is in utils.supabase_client
try:
    from utils.supabase_client import SupabaseClient
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from utils.supabase_client import SupabaseClient

# Constants
NORTH_DAKOTA_AG_BREACH_URL = "https://attorneygeneral.nd.gov/consumer-resources/data-breach-notices"
SOURCE_ID_NORTH_DAKOTA_AG = 15

# Headers for requests - simplified to avoid triggering different content
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# Processing modes
PROCESSING_MODE = os.environ.get("ND_AG_PROCESSING_MODE", "ENHANCED")  # BASIC, ENHANCED, FULL
FILTER_FROM_DATE = os.environ.get("ND_AG_FILTER_FROM_DATE", None)  # Format: YYYY-MM-DD

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

def parse_breach_date_range(date_str: str) -> dict:
    """
    Parse breach date that might be a range like "June 8, 2018 to September 24, 2018"
    or a single date like "February 6, 2019"

    Returns dict with 'start_date', 'end_date', and 'formatted_date'
    For ranges: formatted_date will be "YYYY-MM-DD to YYYY-MM-DD"
    For single dates: formatted_date will be "YYYY-MM-DD"
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', 'ongoing', 'see letter', '']:
        return {'start_date': None, 'end_date': None, 'formatted_date': None}

    date_str = date_str.strip()

    # Check for date range pattern
    if ' to ' in date_str:
        parts = date_str.split(' to ')
        if len(parts) == 2:
            start_date_iso = parse_date_flexible_nd(parts[0].strip())
            end_date_iso = parse_date_flexible_nd(parts[1].strip())

            # Convert to YYYY-MM-DD format for database
            start_date_formatted = None
            end_date_formatted = None

            if start_date_iso:
                try:
                    start_date_formatted = dateutil_parser.parse(start_date_iso).strftime('%Y-%m-%d')
                except:
                    start_date_formatted = None

            if end_date_iso:
                try:
                    end_date_formatted = dateutil_parser.parse(end_date_iso).strftime('%Y-%m-%d')
                except:
                    end_date_formatted = None

            # Create range format for database: "YYYY-MM-DD to YYYY-MM-DD"
            if start_date_formatted and end_date_formatted:
                formatted_date = f"{start_date_formatted} to {end_date_formatted}"
            elif start_date_formatted:
                formatted_date = start_date_formatted  # Fallback to start date if end date parsing failed
            else:
                formatted_date = None

            return {
                'start_date': start_date_iso,
                'end_date': end_date_iso,
                'formatted_date': formatted_date,
                'is_range': True
            }

    # Single date
    single_date_iso = parse_date_flexible_nd(date_str)
    single_date_formatted = None

    if single_date_iso:
        try:
            single_date_formatted = dateutil_parser.parse(single_date_iso).strftime('%Y-%m-%d')
        except:
            single_date_formatted = None

    return {
        'start_date': single_date_iso,
        'end_date': None,
        'formatted_date': single_date_formatted,
        'is_range': False
    }

def parse_affected_individuals(affected_str: str) -> int | None:
    """
    Parse the affected individuals count, handling "Unknown" values
    """
    if not affected_str or affected_str.strip().lower() in ['unknown', 'n/a', 'pending', 'various', 'see notice', 'not provided', '']:
        return None

    # Extract numbers from string
    numbers = re.findall(r'\d+', affected_str.replace(',', ''))
    if numbers:
        try:
            return int(numbers[0])
        except ValueError:
            return None

    return None

def generate_incident_uid(business_name: str, date_reported: str) -> str:
    """
    Generate a unique identifier for the incident using business name and date reported
    """
    if not business_name or not date_reported:
        return None

    # Create a consistent string for hashing
    uid_string = f"{business_name.lower().strip()}_{date_reported}"

    # Generate SHA-256 hash and take first 16 characters
    return hashlib.sha256(uid_string.encode()).hexdigest()[:16]

def should_process_item(date_reported: str) -> bool:
    """
    Check if item should be processed based on date filtering
    """
    if not FILTER_FROM_DATE:
        return True

    try:
        filter_date = datetime.strptime(FILTER_FROM_DATE, "%Y-%m-%d")
        item_date = dateutil_parser.parse(date_reported)
        return item_date.date() >= filter_date.date()
    except (ValueError, TypeError):
        logger.warning(f"Could not parse date for filtering: {date_reported}")
        return True  # Include if we can't parse

def get_table_with_selenium(url: str) -> BeautifulSoup | None:
    """
    Use Selenium to get the JavaScript-rendered table content
    """
    if not SELENIUM_AVAILABLE:
        logger.warning("Selenium not available - cannot handle JavaScript-rendered content")
        return None

    driver = None
    try:
        # Configure Chrome options for headless operation
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        # Initialize the driver
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)

        # Wait for the table to load
        wait = WebDriverWait(driver, 30)
        table_element = wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))

        # Wait a bit more for the table content to populate
        time.sleep(5)

        # Get the page source after JavaScript execution
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        return soup

    except (TimeoutException, WebDriverException) as e:
        logger.error(f"Selenium error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error with Selenium: {e}")
        return None
    finally:
        if driver:
            driver.quit()

def extract_pdf_content(pdf_url: str) -> dict:
    """
    Extract content from PDF document for enhanced analysis.
    Handles both text-based and image-based PDFs.
    """
    if not PDF_PROCESSING_AVAILABLE:
        logger.warning("PDF processing not available - skipping PDF analysis")
        return {
            'pdf_analyzed': False,
            'error': 'PDF processing libraries not available',
            'what_was_leaked': None,
            'pdf_size_bytes': None,
            'pdf_url': pdf_url,
            'extraction_method': None
        }

    try:
        # Download PDF with timeout
        response = requests.get(pdf_url, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()

        pdf_size = len(response.content)
        logger.debug(f"Downloaded PDF: {pdf_size} bytes")

        # Try pdfplumber first
        text_content = ""
        extraction_method = None

        try:
            import io
            pdf_file = io.BytesIO(response.content)

            with pdfplumber.open(pdf_file) as pdf:
                logger.debug(f"PDF has {len(pdf.pages)} pages")
                for page_num, page in enumerate(pdf.pages[:5]):  # Limit to first 5 pages
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        text_content += page_text + "\n"
                        logger.debug(f"Page {page_num + 1}: extracted {len(page_text)} characters")
                    else:
                        logger.debug(f"Page {page_num + 1}: no text extracted")

                if text_content.strip():
                    extraction_method = 'pdfplumber'
                    logger.info(f"pdfplumber extracted {len(text_content)} characters")

        except Exception as e:
            logger.warning(f"pdfplumber failed for {pdf_url}: {e}")

        # Fallback to PyPDF2 if pdfplumber didn't work
        if not text_content.strip():
            try:
                import io
                pdf_file = io.BytesIO(response.content)

                reader = PyPDF2.PdfReader(pdf_file)
                logger.debug(f"PyPDF2: PDF has {len(reader.pages)} pages")

                for page_num in range(min(5, len(reader.pages))):  # Limit to first 5 pages
                    page = reader.pages[page_num]
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        text_content += page_text + "\n"
                        logger.debug(f"PyPDF2 Page {page_num + 1}: extracted {len(page_text)} characters")
                    else:
                        logger.debug(f"PyPDF2 Page {page_num + 1}: no text extracted")

                if text_content.strip():
                    extraction_method = 'PyPDF2'
                    logger.info(f"PyPDF2 extracted {len(text_content)} characters")

            except Exception as e:
                logger.warning(f"PyPDF2 failed for {pdf_url}: {e}")

        # If we successfully extracted text, analyze it
        if text_content.strip():
            what_was_leaked = extract_what_was_leaked_from_text(text_content)
            return {
                'pdf_analyzed': True,
                'what_was_leaked': what_was_leaked,
                'pdf_size_bytes': pdf_size,
                'extraction_method': extraction_method,
                'pdf_url': pdf_url,
                'text_length': len(text_content),
                'text_preview': text_content[:500] if text_content else None
            }

        # If no text could be extracted, it's likely an image-based PDF
        logger.warning(f"No text extracted from PDF {pdf_url} - likely image-based/scanned document")
        return {
            'pdf_analyzed': False,
            'error': 'No text extracted - likely image-based PDF',
            'what_was_leaked': None,
            'pdf_size_bytes': pdf_size,
            'pdf_url': pdf_url,
            'extraction_method': None,
            'requires_ocr': True,
            'fallback_message': 'PDF available for manual review'
        }

    except Exception as e:
        logger.error(f"Error processing PDF {pdf_url}: {e}")
        return {
            'pdf_analyzed': False,
            'error': str(e),
            'what_was_leaked': None,
            'pdf_size_bytes': None,
            'pdf_url': pdf_url,
            'extraction_method': None
        }

def extract_what_was_leaked_from_text(text: str) -> str | None:
    """
    Extract information about what data was leaked from PDF text
    """
    if not text:
        return None

    text_lower = text.lower()

    # Common patterns for data types in breach notifications
    data_patterns = [
        r'information\s+(?:that\s+)?(?:was\s+)?(?:may\s+have\s+been\s+)?(?:involved|compromised|accessed|leaked|stolen)',
        r'types?\s+of\s+information\s+(?:involved|compromised|accessed)',
        r'personal\s+information\s+(?:involved|compromised|accessed)',
        r'data\s+(?:involved|compromised|accessed|leaked)',
        r'information\s+(?:involved|compromised|accessed|leaked)'
    ]

    # Look for sections describing what was leaked
    for pattern in data_patterns:
        matches = re.finditer(pattern, text_lower)
        for match in matches:
            # Extract surrounding context (next 500 characters)
            start_pos = match.start()
            end_pos = min(start_pos + 500, len(text))
            context = text[start_pos:end_pos].strip()

            if len(context) > 50:  # Only return if we have substantial content
                return context

    # Look for common data types mentioned
    data_types = [
        'social security number', 'ssn', 'driver license', 'credit card',
        'bank account', 'medical record', 'health information', 'phi',
        'personal information', 'pii', 'financial information',
        'date of birth', 'address', 'phone number', 'email'
    ]

    found_types = []
    for data_type in data_types:
        if data_type in text_lower:
            found_types.append(data_type)

    if found_types:
        return f"Data types mentioned: {', '.join(found_types[:10])}"  # Limit to first 10

    return None

def process_north_dakota_ag_breaches():
    """
    Enhanced North Dakota AG Data Breach Notice processing with 3-tier data structure.
    Processes the modern table format on the ND AG website.
    """
    logger.info(f"Starting North Dakota AG Data Breach Notice processing in {PROCESSING_MODE} mode...")

    if FILTER_FROM_DATE:
        logger.info(f"Filtering breaches from date: {FILTER_FROM_DATE}")

    # First try with regular requests
    soup = None
    try:
        response = requests.get(NORTH_DAKOTA_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching North Dakota AG breach data page: {e}")
        return

    # Find the main data table (FooTable format)
    # The table might be dynamically loaded, so let's look for various table selectors
    table = soup.find('table')
    logger.debug(f"First table search result: {table is not None}")

    if not table:
        # Try alternative selectors
        table = soup.find('table', {'id': 'footable_439'})
        logger.debug(f"ID search result: {table is not None}")
    if not table:
        table = soup.find('table', class_=lambda x: x and 'footable' in x)
        logger.debug(f"Footable class search result: {table is not None}")
    if not table:
        table = soup.find('table', class_=lambda x: x and 'ninja_table' in x)
        logger.debug(f"Ninja table class search result: {table is not None}")

    # Check if table has actual data rows
    if table:
        logger.info("Table found! Checking for data rows...")
        # Look for tbody first, then fallback to direct tr elements
        tbody = table.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
            logger.info(f"Found {len(rows)} rows in tbody")
        else:
            rows = table.find_all('tr')[1:]  # Skip header row if no tbody
            logger.info(f"Found {len(rows)} rows in table (skipped header)")

        if not rows or len(rows) < 5:  # If no rows or very few rows, table might be empty
            logger.warning(f"Table found but has only {len(rows) if rows else 0} data rows - might be dynamically loaded")
            table = None
        else:
            logger.info(f"Table validation passed - {len(rows)} rows found")

    # If no table found or table is empty, try Selenium
    if not table:
        logger.info("Table not found or empty with requests - trying Selenium for JavaScript-rendered content...")
        soup = get_table_with_selenium(NORTH_DAKOTA_AG_BREACH_URL)
        if soup:
            table = soup.find('table')
            if table:
                logger.info("Successfully retrieved table using Selenium")
            else:
                logger.error("Even Selenium could not find the table")
                return
        else:
            logger.error("Could not retrieve page content with Selenium")
            return

    # Get table rows (skip header row)
    tbody = table.find('tbody')
    if tbody:
        rows = tbody.find_all('tr')  # tbody rows don't include header
    else:
        rows = table.find_all('tr')[1:]  # Skip header row if no tbody

    if not rows:
        logger.error("No data rows found in the table")
        return

    logger.info(f"Found {len(rows)} breach notification rows to process.")

    supabase_client = None
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    total_processed = 0
    total_inserted = 0
    total_skipped = 0

    # Process each table row
    for row_idx, row in enumerate(rows):
        total_processed += 1

        try:
            # Extract table cells
            cells = row.find_all('td')
            if len(cells) < 6:
                logger.warning(f"Row {row_idx + 1} has insufficient columns ({len(cells)}). Skipping.")
                total_skipped += 1
                continue

            # Extract data from table columns
            # Columns: Business Name | Doing Business As | Date of Breach | Date Reported | ND Residents Affected | Notification Document
            business_name = cells[0].get_text(strip=True)
            doing_business_as = cells[1].get_text(strip=True)
            date_of_breach = cells[2].get_text(strip=True)
            date_reported = cells[3].get_text(strip=True)
            nd_residents_affected = cells[4].get_text(strip=True)

            # Extract PDF download link
            pdf_link_cell = cells[5]
            pdf_link = pdf_link_cell.find('a')
            pdf_url = None
            if pdf_link and pdf_link.get('href'):
                pdf_url = urljoin(NORTH_DAKOTA_AG_BREACH_URL, pdf_link['href'])

            # Validate required fields
            if not business_name or not date_reported:
                logger.warning(f"Row {row_idx + 1} missing required fields (business_name: '{business_name}', date_reported: '{date_reported}'). Skipping.")
                total_skipped += 1
                continue

            # Check date filtering
            if not should_process_item(date_reported):
                logger.debug(f"Skipping '{business_name}' - outside date filter range")
                total_skipped += 1
                continue

            # Parse dates
            breach_date_info = parse_breach_date_range(date_of_breach)
            reported_date_iso = parse_date_flexible_nd(date_reported)

            if not reported_date_iso:
                logger.warning(f"Skipping '{business_name}' due to unparsable reported date: '{date_reported}'")
                total_skipped += 1
                continue

            # Parse affected individuals count
            affected_count = parse_affected_individuals(nd_residents_affected)

            # Generate unique incident ID
            incident_uid = generate_incident_uid(business_name, date_reported)

            # Prepare tier 1 data (basic table data)
            tier1_data = {
                "business_name": business_name,
                "doing_business_as": doing_business_as if doing_business_as else None,
                "date_of_breach": date_of_breach,
                "date_reported": date_reported,
                "nd_residents_affected": nd_residents_affected,
                "pdf_url": pdf_url,
                "breach_date_parsed": breach_date_info,
                "affected_individuals_parsed": affected_count
            }

            # Prepare tier 2 data (enhanced processing)
            tier2_data = {}
            extracted_what_was_leaked = None

            if PROCESSING_MODE in ["ENHANCED", "FULL"] and pdf_url:
                logger.info(f"Analyzing PDF for '{business_name}'...")
                pdf_analysis = extract_pdf_content(pdf_url)
                tier2_data.update(pdf_analysis)

                # Extract what_was_leaked for the main field
                extracted_what_was_leaked = pdf_analysis.get('what_was_leaked')

                # If we couldn't extract text but have a PDF, store PDF URL as fallback
                if not pdf_analysis.get('pdf_analyzed', False):
                    logger.info(f"PDF analysis failed for '{business_name}' - storing PDF URL for manual review")
                    extracted_what_was_leaked = pdf_url  # Store PDF URL as fallback

                # Add small delay to avoid overwhelming the server
                time.sleep(random.uniform(1, 3))
            elif pdf_url:
                # Even in BASIC mode, store the PDF URL for potential future analysis
                tier2_data['pdf_url'] = pdf_url
                tier2_data['pdf_analysis_skipped'] = 'BASIC mode - PDF available for manual review'
                extracted_what_was_leaked = pdf_url  # Store PDF URL as fallback in BASIC mode too

            # Prepare tier 3 data (full analysis - placeholder for future enhancements)
            tier3_data = {}
            if PROCESSING_MODE == "FULL":
                # Future: Additional analysis, cross-referencing, etc.
                tier3_data["processing_mode"] = "FULL"
                tier3_data["processing_timestamp"] = datetime.now().isoformat()

            # Combine all raw data
            raw_data_json = {
                "tier1_basic_data": tier1_data,
                "tier2_enhanced_data": tier2_data,
                "tier3_full_data": tier3_data,
                "processing_mode": PROCESSING_MODE,
                "scraper_version": "2.0_enhanced"
            }

            # Prepare tags
            tags = ["north_dakota_ag", "nd_ag", "table_format"]
            if breach_date_info.get('start_date'):
                try:
                    breach_year = dateutil_parser.parse(breach_date_info['start_date']).year
                    tags.append(f"year_{breach_year}")
                except:
                    pass

            # Prepare final item data for Supabase
            item_data = {
                "source_id": SOURCE_ID_NORTH_DAKOTA_AG,
                "title": business_name,
                "item_url": pdf_url if pdf_url else NORTH_DAKOTA_AG_BREACH_URL,
                "publication_date": reported_date_iso,
                "reported_date": reported_date_iso,
                "breach_date": breach_date_info.get('formatted_date'),
                "affected_individuals": affected_count,
                "notice_document_url": pdf_url,
                "what_was_leaked": extracted_what_was_leaked or tier2_data.get('what_was_leaked'),
                "tags_keywords": tags,
                "raw_data_json": raw_data_json
            }

            # Store incident_uid in raw_data_json since it's not a direct field
            raw_data_json["incident_uid"] = incident_uid

            # Insert into Supabase
            insert_response = supabase_client.insert_item(**item_data)
            if insert_response:
                logger.info(f"Successfully inserted '{business_name}' (Affected: {affected_count or 'Unknown'}, PDF: {'Yes' if pdf_url else 'No'})")
                total_inserted += 1
            else:
                logger.error(f"Failed to insert '{business_name}'")
                total_skipped += 1

        except Exception as e:
            logger.error(f"Error processing row {row_idx + 1}: {e}", exc_info=True)
            total_skipped += 1

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
