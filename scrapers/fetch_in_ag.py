import os
import re
import io
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
from dateutil import parser as dateutil_parser
import time

# Assuming SupabaseClient is in utils.supabase_client
try:
    from utils.supabase_client import SupabaseClient, clean_text_for_database
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from utils.supabase_client import SupabaseClient, clean_text_for_database

# Setup comprehensive logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Enhanced Constants for Indiana AG
INDIANA_AG_BREACH_URL = "https://www.in.gov/attorneygeneral/2874.htm"
SOURCE_ID_INDIANA_AG = 7

# Configuration from environment variables
FILTER_FROM_DATE = os.environ.get("IN_AG_FILTER_FROM_DATE")  # Format: YYYY-MM-DD
PROCESSING_MODE = os.environ.get("IN_AG_PROCESSING_MODE", "ENHANCED")  # BASIC, ENHANCED, FULL

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Rate limiting
RATE_LIMIT_DELAY = 2  # seconds between requests

def rate_limit_delay():
    """Add rate limiting delay between requests."""
    time.sleep(RATE_LIMIT_DELAY)

def parse_date_flexible_in(date_str: str) -> str | None:
    """
    Enhanced date parsing for Indiana AG breach data.
    Returns ISO 8601 format string or None if parsing fails.
    """
    if not date_str or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided', 'ongoing']:
        return None

    # Clean the date string
    date_str = date_str.strip()

    try:
        # Handle common Indiana AG date formats
        dt_object = dateutil_parser.parse(date_str)
        return dt_object.isoformat()
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def extract_affected_individuals_in(text: str) -> int | None:
    """
    Extract number of affected individuals from text.
    Handles various formats like "1,234", "approximately 500", "up to 1000", etc.
    """
    if not text:
        return None

    # Clean text and convert to lowercase
    text = text.lower().strip()

    # Skip non-numeric indicators
    if any(skip_word in text for skip_word in ['unknown', 'n/a', 'pending', 'investigating', 'tbd']):
        return None

    # Extract numbers using regex - handle both comma-separated and simple numbers
    # First try to find comma-separated numbers (like "1,234" or "10,000")
    comma_pattern = r'\b(\d{1,3}(?:,\d{3})+)\b'
    comma_matches = re.findall(comma_pattern, text)
    if comma_matches:
        try:
            # Convert comma-separated numbers
            numbers = [int(match.replace(',', '')) for match in comma_matches]
            return max(numbers)
        except ValueError:
            pass

    # If no comma-separated numbers, look for simple numbers
    simple_pattern = r'\b(\d+)\b'
    simple_matches = re.findall(simple_pattern, text)
    if simple_matches:
        try:
            # Take the largest number found (often the most relevant)
            numbers = [int(match) for match in simple_matches]
            return max(numbers)
        except ValueError:
            pass

    return None

def generate_incident_uid_in(year: str, index: int) -> str:
    """
    Generate unique incident identifier for Indiana AG breaches.
    Format: IN-AG-{year}-{index:03d}
    """
    return f"IN-AG-{year}-{index:03d}"

def get_yearly_pdf_urls() -> dict:
    """
    Extract yearly PDF URLs from the main Indiana AG breach page.
    Returns dict with year as key and PDF URL as value.
    """
    try:
        logger.info("Fetching yearly PDF URLs from Indiana AG breach page...")
        response = requests.get(INDIANA_AG_BREACH_URL, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the content area - updated for current page structure
        content_area = soup.find('section', id='content_container_324572')
        if not content_area:
            content_area = soup.find('div', id='contentcontainer')
            if not content_area:
                content_area = soup.find('article', class_='main-content')
                if not content_area:
                    logger.error("Could not find main content area on Indiana AG page")
                    return {}

        # Find all PDF links with year patterns
        pdf_urls = {}
        pdf_links = content_area.find_all('a', href=lambda href: href and href.lower().endswith('.pdf'))

        for link in pdf_links:
            href = link.get('href', '')
            link_text = link.get_text(strip=True)

            # Extract year from link text or filename
            year_match = re.search(r'\b(20\d{2})\b', link_text + ' ' + href)
            if year_match:
                year = year_match.group(1)
                full_url = urljoin(INDIANA_AG_BREACH_URL, href)
                pdf_urls[year] = full_url
                logger.info(f"Found PDF for year {year}: {full_url}")

        logger.info(f"Found {len(pdf_urls)} yearly PDF reports")
        return pdf_urls

    except Exception as e:
        logger.error(f"Error fetching yearly PDF URLs: {e}")
        return {}

def parse_pdf_table_data(pdf_url: str, year: str) -> list:
    """
    Parse tabular breach data from Indiana AG yearly PDF reports.
    Returns list of breach records extracted from the PDF.
    """
    try:
        logger.info(f"Parsing PDF table data for year {year}: {pdf_url}")

        # Add rate limiting
        rate_limit_delay()

        # Download PDF
        response = requests.get(pdf_url, headers=REQUEST_HEADERS, timeout=60)
        response.raise_for_status()

        breach_records = []

        # Try pdfplumber first (better for tables)
        try:
            import pdfplumber
            pdf_file = io.BytesIO(response.content)

            with pdfplumber.open(pdf_file) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    # Extract tables from the page
                    tables = page.extract_tables()

                    for table in tables:
                        if not table:
                            continue

                        # Process table rows
                        for row_idx, row in enumerate(table):
                            if not row or len(row) < 3:  # Skip incomplete rows
                                continue

                            # Skip header rows and invalid data
                            row_text = ' '.join(str(cell) for cell in row if cell).lower()
                            if any(header in row_text for header in ['organization', 'entity', 'company', 'date', 'breach', 'affected', 'notification', 'report']):
                                continue

                            # Skip rows where first column is just a number (row numbers)
                            if len(row) > 1 and str(row[0]).strip().isdigit() and len(str(row[0]).strip()) < 4:
                                # This looks like a row number, use the corrected column mapping
                                pass
                            elif not str(row[0]).strip().isdigit():
                                # This might be old format, skip for now
                                continue

                            # Extract breach record data - CORRECT COLUMN MAPPING
                            # Based on PDF visual inspection, the actual column order is:
                            # Column 0: ROW NO (Row Number - skip)
                            # Column 1: Matter:Name (Organization Name)
                            # Column 2: Notific Sent (Notification Sent Date)
                            # Column 3: Breach Occ (Breach Occurred Date)
                            # Column 4: IN Affected (Indiana Residents Affected)
                            # Column 5: Total Affected (Total People Affected Across All States)
                            record = {
                                'organization_name': str(row[1]).strip() if len(row) > 1 and row[1] else '',
                                'notification_sent_date': str(row[2]).strip() if len(row) > 2 and row[2] else '',
                                'breach_date': str(row[3]).strip() if len(row) > 3 and row[3] else '',
                                'indiana_affected': str(row[4]).strip() if len(row) > 4 and row[4] else '',
                                'total_affected': str(row[5]).strip() if len(row) > 5 and row[5] else '',
                                'pdf_url': pdf_url,
                                'year': year,
                                'page_number': page_num + 1,
                                'row_index': row_idx
                            }

                            # Validate record has essential data
                            if record['organization_name'] and record['organization_name'] not in ['None', 'null', '']:
                                breach_records.append(record)
                                logger.debug(f"Valid record found: {record['organization_name']} - IN: {record['indiana_affected']}, Total: {record['total_affected']}")
                            else:
                                logger.debug(f"Skipped invalid record: {record}")

        except ImportError:
            logger.warning("pdfplumber not available, trying PyPDF2...")
            # Fallback to PyPDF2 (less reliable for tables)
            try:
                import PyPDF2
                pdf_file = io.BytesIO(response.content)
                pdf_reader = PyPDF2.PdfReader(pdf_file)

                full_text = ""
                for page in pdf_reader.pages:
                    full_text += page.extract_text() + "\n"

                # Simple text parsing for table-like data
                lines = full_text.split('\n')
                for line_idx, line in enumerate(lines):
                    line = line.strip()
                    if not line or len(line) < 10:
                        continue

                    # Look for lines that might contain breach data
                    # This is a simplified approach and may need refinement
                    if any(keyword in line.lower() for keyword in ['corp', 'inc', 'llc', 'company', 'hospital', 'medical']):
                        record = {
                            'organization_name': line[:50],  # First part likely org name
                            'breach_date': '',
                            'reported_date': '',
                            'affected_individuals': '',
                            'information_compromised': line,
                            'pdf_url': pdf_url,
                            'year': year,
                            'page_number': 1,
                            'row_index': line_idx
                        }
                        breach_records.append(record)

            except Exception as e:
                logger.error(f"PyPDF2 parsing failed: {e}")

        logger.info(f"Extracted {len(breach_records)} breach records from {year} PDF")
        return breach_records

    except Exception as e:
        logger.error(f"Error parsing PDF {pdf_url}: {e}")
        return []

def should_process_record(record: dict) -> bool:
    """
    Determine if a breach record should be processed based on date filtering.
    """
    if not FILTER_FROM_DATE:
        return True

    try:
        filter_date = datetime.strptime(FILTER_FROM_DATE, "%Y-%m-%d")

        # Try to parse breach date or notification sent date
        for date_field in ['notification_sent_date', 'breach_date']:
            date_str = record.get(date_field, '')
            if date_str:
                parsed_date = parse_date_flexible_in(date_str)
                if parsed_date:
                    record_date = datetime.fromisoformat(parsed_date.replace('Z', '+00:00'))
                    return record_date.date() >= filter_date.date()

        # If no valid date found, include the record
        return True

    except Exception as e:
        logger.warning(f"Error in date filtering: {e}")
        return True

def process_indiana_ag_breaches():
    """
    Enhanced Indiana AG Security Breach Notification processing with 3-tier data structure.
    Processes yearly PDF reports to extract individual breach records.
    """
    logger.info("Starting Enhanced Indiana AG Security Breach Notification processing...")
    logger.info(f"Processing mode: {PROCESSING_MODE}")
    logger.info(f"Date filter: {FILTER_FROM_DATE or 'None (all records)'}")

    # Initialize Supabase client
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return

    # Step 1: Get yearly PDF URLs
    yearly_pdfs = get_yearly_pdf_urls()
    if not yearly_pdfs:
        logger.error("No yearly PDF reports found")
        return

    # Focus only on 2025 data as requested
    if '2025' in yearly_pdfs:
        years_to_process = ['2025']
    else:
        logger.error("2025 PDF not found in yearly reports")
        return

    logger.info(f"Processing {len(years_to_process)} years: {years_to_process}")

    total_processed = 0
    total_inserted = 0
    total_skipped = 0

    # Step 2: Process each yearly PDF
    for year in sorted(years_to_process, reverse=True):  # Process newest first
        pdf_url = yearly_pdfs[year]
        logger.info(f"Processing {year} PDF: {pdf_url}")

        # Extract breach records from PDF
        breach_records = parse_pdf_table_data(pdf_url, year)
        if not breach_records:
            logger.warning(f"No breach records found in {year} PDF")
            continue

        # Step 3: Process each breach record
        for record_idx, record in enumerate(breach_records):
            total_processed += 1

            try:
                # Apply date filtering
                if not should_process_record(record):
                    logger.debug(f"Skipping record due to date filter: {record.get('organization_name', 'Unknown')}")
                    total_skipped += 1
                    continue

                # Generate unique identifiers
                incident_uid = generate_incident_uid_in(year, record_idx + 1)
                unique_url = f"{INDIANA_AG_BREACH_URL}#{year}-breach-{record_idx + 1:03d}"

                # Parse dates
                breach_date_iso = parse_date_flexible_in(record.get('breach_date', ''))
                notification_sent_date_iso = parse_date_flexible_in(record.get('notification_sent_date', ''))

                # Extract affected individuals (both Indiana and total)
                indiana_affected = extract_affected_individuals_in(record.get('indiana_affected', ''))
                total_affected = extract_affected_individuals_in(record.get('total_affected', ''))

                # Note: Indiana AG PDF does not contain data types information
                data_types_compromised = []

                # Build 3-tier data structure
                raw_data = {
                    # Tier 1: Portal Data (Raw extraction from PDF)
                    "tier_1_portal_data": {
                        "pdf_url": pdf_url,
                        "pdf_year": year,
                        "extraction_timestamp": datetime.now().isoformat(),
                        "page_number": record.get('page_number'),
                        "row_index": record.get('row_index'),
                        "raw_organization_name": record.get('organization_name', ''),
                        "raw_breach_date": record.get('breach_date', ''),
                        "raw_notification_sent_date": record.get('notification_sent_date', ''),
                        "raw_indiana_affected": record.get('indiana_affected', ''),
                        "raw_total_affected": record.get('total_affected', ''),
                        "processing_mode": PROCESSING_MODE,
                        "affected_individuals_scope": "Both Indiana residents and total affected available"
                    },

                    # Tier 2: Derived/Enrichment (Computed fields)
                    "tier_2_derived_data": {
                        "incident_uid": incident_uid,
                        "portal_first_seen_utc": datetime.now().isoformat(),
                        "portal_last_seen_utc": datetime.now().isoformat(),
                        "breach_record_index": record_idx + 1,
                        "data_types_normalized": data_types_compromised,
                        "indiana_affected_parsed": indiana_affected,
                        "total_affected_parsed": total_affected,
                        "breach_date_parsed": breach_date_iso,
                        "notification_sent_date_parsed": notification_sent_date_iso,
                        "extraction_confidence": "high" if all([
                            record.get('organization_name'),
                            record.get('breach_date') or record.get('notification_sent_date')
                        ]) else "medium"
                    },

                    # Tier 3: Deep Analysis (Enhanced processing)
                    "tier_3_deep_analysis": {
                        "data_types_detailed": data_types_compromised,
                        "incident_timeline": {
                            "breach_date": breach_date_iso,
                            "notification_sent_date": notification_sent_date_iso
                        },
                        "regulatory_context": {
                            "state": "Indiana",
                            "reporting_authority": "Indiana Attorney General",
                            "disclosure_law": "Indiana Data Breach Notification Law"
                        },
                        "analysis_timestamp": datetime.now().isoformat()
                    }
                }

                # Clean organization name
                org_name = clean_text_for_database(record.get('organization_name', '').strip())
                if not org_name:
                    logger.warning(f"Skipping record with empty organization name")
                    total_skipped += 1
                    continue

                # Build summary
                summary_parts = [f"Data breach notification for {org_name}"]
                if total_affected:
                    summary_parts.append(f"affecting {total_affected:,} total individuals")
                if indiana_affected:
                    summary_parts.append(f"including {indiana_affected:,} Indiana residents")
                summary_parts.append("reported to Indiana Attorney General")
                summary = ". ".join(summary_parts) + "."

                # Enhanced tags
                tags = ["indiana_ag", "in_breach", "data_breach", f"year_{year}"]
                for data_type in data_types_compromised:
                    if "Social Security" in data_type:
                        tags.append("ssn_breach")
                    elif "Medical" in data_type:
                        tags.append("healthcare_breach")
                    elif "Financial" in data_type:
                        tags.append("financial_breach")

                # Prepare item data for database
                item_data = {
                    "source_id": SOURCE_ID_INDIANA_AG,
                    "item_url": unique_url,
                    "title": org_name,
                    "publication_date": notification_sent_date_iso or breach_date_iso,
                    "summary_text": summary,
                    "raw_data_json": raw_data,
                    "tags_keywords": list(set(tags)),

                    # Standardized breach fields (now with total affected individuals)
                    "affected_individuals": total_affected,  # Total affected across all states
                    "breach_date": breach_date_iso.split('T')[0] if breach_date_iso else None,
                    "reported_date": notification_sent_date_iso.split('T')[0] if notification_sent_date_iso else None,
                    "notice_document_url": pdf_url,

                    # Enhanced fields
                    "data_types_compromised": data_types_compromised,
                    "keywords_detected": ["indiana", "breach", "notification", "attorney_general"],
                    "file_size_bytes": None,  # Could be added if needed

                    # Note: what_was_leaked not available in Indiana AG PDF format
                    # Note: indiana_residents_affected stored in raw_data_json tier_2_derived_data
                }

                # Check for existing record
                enhancement_status = supabase_client.get_item_enhancement_status(unique_url)
                if enhancement_status.get('exists'):
                    logger.info(f"Record already exists for {org_name} ({year}), skipping")
                    total_skipped += 1
                    continue

                # Insert into database
                insert_response = supabase_client.insert_item(**item_data)
                if insert_response:
                    logger.info(f"Successfully inserted: {org_name} ({year}) - {total_affected or 'Unknown'} total affected, {indiana_affected or 'Unknown'} IN residents")
                    total_inserted += 1
                else:
                    logger.error(f"Failed to insert: {org_name} ({year})")
                    total_skipped += 1

            except Exception as e:
                logger.error(f"Error processing breach record {record_idx + 1} from {year}: {e}", exc_info=True)
                total_skipped += 1

    logger.info(f"Enhanced Indiana AG processing complete:")
    logger.info(f"  Total records processed: {total_processed}")
    logger.info(f"  Successfully inserted: {total_inserted}")
    logger.info(f"  Skipped: {total_skipped}")
    logger.info(f"  Processing mode: {PROCESSING_MODE}")
    logger.info(f"  Years processed: {years_to_process}")

if __name__ == "__main__":
    logger.info("Enhanced Indiana AG Security Breach Scraper Started")
    logger.info(f"Processing mode: {PROCESSING_MODE}")
    logger.info(f"Date filter: {FILTER_FROM_DATE or 'None (all records)'}")

    # Validate environment variables
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
        exit(1)
    else:
        logger.info("Supabase environment variables configured")

        try:
            process_indiana_ag_breaches()
            logger.info("Enhanced Indiana AG Security Breach Scraper completed successfully")
        except Exception as e:
            logger.error(f"Critical error in Indiana AG scraper: {e}", exc_info=True)
            exit(1)

    logger.info("Enhanced Indiana AG Security Breach Scraper Finished")
