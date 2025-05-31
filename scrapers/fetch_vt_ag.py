import os
import logging
import requests
import hashlib
import time
import random
import re
import io
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from urllib.parse import urljoin
from dateutil import parser as dateutil_parser

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
VERMONT_AG_BREACH_URL = "https://ago.vermont.gov/categories/security-breach-notices"
SOURCE_ID_VERMONT_AG = 17

# Configuration for date filtering
# Set to None to collect all historical data (for testing)
# Set to a date string like "2025-01-27" for production filtering
# Default to one week back for better testing coverage
default_date = (date.today() - timedelta(days=7)).strftime('%Y-%m-%d')
FILTER_FROM_DATE = os.environ.get("VT_AG_FILTER_FROM_DATE", default_date)

# Processing mode configuration
# BASIC: Only page titles and URLs (fast, reliable for daily collection)
# ENHANCED: Individual page processing with PDF URLs (moderate speed, good for regular collection)
# FULL: Everything including PDF analysis (slow, for research/analysis)
PROCESSING_MODE = os.environ.get("VT_AG_PROCESSING_MODE", "ENHANCED")  # BASIC, ENHANCED, FULL

# Rate limiting configuration
MIN_DELAY_SECONDS = 2  # Minimum delay between requests
MAX_DELAY_SECONDS = 5  # Maximum delay between requests
REQUEST_TIMEOUT = 60   # Increased timeout for PDF downloads
MAX_RETRIES = 3        # Maximum number of retries for failed requests

# Headers for requests
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://ago.vermont.gov/'
}

def generate_incident_uid(organization_name: str, reported_date: str) -> str:
    """
    Generate a unique incident identifier for deduplication using organization name and date.
    """
    # Create a unique string combining organization and date
    unique_string = f"vt_ag_{organization_name}_{reported_date}".lower().replace(" ", "_")
    # Generate a hash for consistent UIDs
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

def parse_date_flexible(date_str: str) -> str | None:
    """
    Tries to parse a date string using dateutil.parser for flexibility.
    Returns ISO format date string or None if parsing fails.
    """
    if not date_str or date_str.strip() == "" or date_str.strip().lower() in ['n/a', 'unknown', 'pending', 'various', 'see notice', 'not provided']:
        return None

    try:
        # Clean up the date string
        date_str = date_str.strip()

        # Parse the date from YYYY-MM-DD format (Vermont AG standard)
        parsed_date = dateutil_parser.parse(date_str)
        return parsed_date.strftime('%Y-%m-%d')
    except (ValueError, TypeError, OverflowError) as e:
        logger.warning(f"Could not parse date string: '{date_str}'. Error: {e}")
        return None

def parse_organization_name_from_title(title: str) -> str:
    """
    Extract organization name from Vermont AG page title format:
    "YYYY-MM-DD Organization Name Data Breach Notice to Consumers"
    """
    if not title:
        return "Unknown Organization"

    # Remove the date prefix (YYYY-MM-DD)
    title_without_date = re.sub(r'^\d{4}-\d{2}-\d{2}\s+', '', title)

    # Remove the suffix "Data Breach Notice to Consumers"
    org_name = re.sub(r'\s+Data\s+Breach\s+Notice\s+to\s+Consumers.*$', '', title_without_date, flags=re.IGNORECASE)

    return org_name.strip()

def parse_date_from_title(title: str) -> str | None:
    """
    Extract date from Vermont AG page title format:
    "YYYY-MM-DD Organization Name Data Breach Notice to Consumers"
    """
    if not title:
        return None

    # Extract YYYY-MM-DD from the beginning of the title
    date_match = re.match(r'^(\d{4}-\d{2}-\d{2})', title)
    if date_match:
        return date_match.group(1)

    return None

def rate_limit_delay():
    """
    Add a random delay between requests to avoid overwhelming the server.
    """
    delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
    logger.debug(f"Rate limiting: waiting {delay:.1f} seconds")
    time.sleep(delay)

def should_process_breach(reported_date: str) -> bool:
    """
    Check if a breach should be processed based on date filtering configuration.
    """
    if not FILTER_FROM_DATE:
        return True  # No filtering, process all

    if not reported_date:
        return True  # Process if we can't determine date

    try:
        breach_date = datetime.strptime(reported_date, '%Y-%m-%d').date()
        filter_date = datetime.strptime(FILTER_FROM_DATE, '%Y-%m-%d').date()
        return breach_date >= filter_date
    except (ValueError, TypeError):
        logger.warning(f"Could not compare dates for filtering: breach_date={reported_date}, filter_date={FILTER_FROM_DATE}")
        return True  # Process if date comparison fails

def extract_what_information_involved(content: str) -> dict:
    """
    Extract information about what data was compromised from Vermont AG breach notifications.
    Enhanced with Vermont AG-specific patterns.
    """
    result = {
        'what_information_involved_text': None,
        'extraction_method': None,
        'confidence': 'none'
    }

    # Enhanced patterns for Vermont AG PDFs - ordered by confidence/specificity
    section_patterns = [
        # Vermont AG condensed format (no spaces) - highest priority
        r'WhatInformationWasInvolved\.?(.+?)(?=What|$)',
        r'Thedatathatmayhavebeenaccessedwithoutauthorizationincluded(.+?)(?=\.|What|$)',
        r'mayhavebeenaccessedwithoutauthorizationincluded(.+?)(?=\.|What|$)',

        # Vermont AG specific patterns (high confidence)
        r'what information was involved\.?\s*(.+?)(?=what (?:we|are|the)|how to protect|steps you can take|$)',

        # Vermont AG condensed format: "The data that may have been accessed..."
        r'the data that may have been accessed (?:without authorization )?(?:included|includes?)\s*(.+?)(?=\.|what (?:we|are)|how to|steps|$)',

        # Vermont AG format: "may have been accessed without authorization included"
        r'may have been accessed without authorization included\s*(.+?)(?=\.|what (?:we|are)|how to|steps|$)',

        # Standard format: "What information was involved?" until next section
        r'what information was involved\?[\s\n]*(.+?)(?=what we are doing|what are we doing)',

        # Alternative: "What personal information was affected?"
        r'what personal information was affected\?[\s\n]*(.+?)(?=what (?:we|are|the))',

        # Alternative: "What data was compromised?"
        r'what data was compromised\?[\s\n]*(.+?)(?=what (?:we|are|the))',

        # Alternative: "Information involved" section
        r'information involved[\s\n]*(.+?)(?=\n\s*what [a-zA-Z\s]+\?)',

        # Look for "The following information" patterns
        r'the following information[^.]*:[\s\n]*(.+?)(?=\n\s*\n|\n\s*for more information|$)',

        # Look for "may have included" patterns
        r'may have included[\s\n]*(.+?)(?=\n\s*\n|\n\s*for more information|$)',

        # Vermont AG pattern: "your name and [data types]"
        r'your name and\s*(.+?)(?=\.|what (?:we|are)|how to|steps|$)',

        # Vermont AG condensed pattern: "yourname and [data types]"
        r'yournameand(.+?)(?=\.|What|$)',

        # Broader pattern for data types listing
        r'(?:included|includes?|contained|contains?)\s*(?:your\s+)?(.+?(?:name|address|social security|ssn|date of birth|phone|email|account).+?)(?=\.|what (?:we|are)|how to|steps|$)',
    ]

    for i, pattern in enumerate(section_patterns):
        matches = re.finditer(pattern, content, re.IGNORECASE | re.DOTALL)
        for match in matches:
            extracted_text = match.group(1).strip()

            # Clean up the extracted text but preserve structure
            extracted_text = re.sub(r'\n\s*\n', '\n\n', extracted_text)  # Normalize paragraph breaks
            extracted_text = re.sub(r'[ \t]+', ' ', extracted_text)  # Normalize spaces but keep newlines
            extracted_text = extracted_text.strip()

            # Clean up Vermont AG condensed format by adding spaces
            if i < 3:  # Only for condensed format patterns
                # Add spaces before capital letters (but not at start)
                extracted_text = re.sub(r'(?<!^)(?=[A-Z])', ' ', extracted_text)
                # Fix common concatenated words
                extracted_text = re.sub(r'yournameand', 'your name and', extracted_text, flags=re.IGNORECASE)
                extracted_text = re.sub(r'socialsecuritynumber', 'social security number', extracted_text, flags=re.IGNORECASE)
                extracted_text = re.sub(r'dateofbirth', 'date of birth', extracted_text, flags=re.IGNORECASE)
                extracted_text = re.sub(r'phonenumber', 'phone number', extracted_text, flags=re.IGNORECASE)
                extracted_text = re.sub(r'emailaddress', 'email address', extracted_text, flags=re.IGNORECASE)
                # Clean up extra spaces
                extracted_text = re.sub(r'\s+', ' ', extracted_text).strip()

            # Skip if too short (likely not the real section)
            if len(extracted_text) < 15:  # Reduced threshold for condensed format
                continue

            # Skip if it looks like just a question or header
            if extracted_text.strip().endswith('?') and len(extracted_text) < 100:
                continue

            result['what_information_involved_text'] = extracted_text
            result['extraction_method'] = f'vt_pattern_{i+1}'
            result['confidence'] = 'high' if i < 6 else 'medium'  # Adjusted for new patterns
            return result

    return result

def extract_affected_individuals_from_pdf(content: str) -> dict:
    """
    Enhanced extraction of affected individuals count from PDF content.
    Optimized for Vermont AG PDF patterns.
    """
    result = {
        'count': None,
        'raw_text': None,
        'confidence': 'none',
        'extraction_method': None
    }

    # Enhanced patterns for affected individuals with priority order
    # Added Vermont AG specific patterns based on actual PDF content
    patterns = [
        # High confidence patterns (specific numbers with clear context)
        (r'(?:exactly|precisely)\s+(\d+(?:,\d+)*)\s+(?:individuals?|people|persons?|vermont residents?)', 'high', 'exact_count'),
        (r'(\d+(?:,\d+)*)\s+(?:vermont residents?|individuals?|people|persons?)\s+(?:were|are|have been)\s+(?:affected|impacted|involved|compromised)', 'high', 'direct_statement'),
        (r'(?:affects?|impacts?|involves?)\s+(\d+(?:,\d+)*)\s+(?:vermont residents?|individuals?|people|persons?)', 'high', 'affects_statement'),

        # Vermont AG specific patterns
        (r'this incident (?:affects?|impacts?) (\d+(?:,\d+)*)', 'high', 'vt_ag_incident_affects'),
        (r'breach (?:affects?|impacts?) (\d+(?:,\d+)*)', 'high', 'vt_ag_breach_affects'),
        (r'notification (?:to|for) (\d+(?:,\d+)*)', 'high', 'vt_ag_notification_count'),

        # Vermont AG condensed format patterns
        (r'(\d+(?:,\d+)*)\s+(?:current and former|current or former)?\s*(?:customers?|clients?|patients?|members?)', 'medium', 'vt_ag_customers'),
        (r'(?:involving|affecting)\s+(\d+(?:,\d+)*)\s+(?:individuals?|people|persons?)', 'high', 'vt_ag_involving'),
        (r'(\d+(?:,\d+)*)\s+(?:individuals?|people|persons?)\s+(?:may have been|were potentially)', 'high', 'vt_ag_potentially_affected'),

        # Medium confidence patterns (approximate numbers)
        (r'(?:approximately|about|around|roughly)\s+(\d+(?:,\d+)*)\s+(?:vermont residents?|individuals?|people|persons?)', 'medium', 'approximate'),
        (r'(?:up to|as many as|no more than)\s+(\d+(?:,\d+)*)\s+(?:vermont residents?|individuals?|people|persons?)', 'medium', 'upper_bound'),
        (r'(?:over|more than|at least|minimum of)\s+(\d+(?:,\d+)*)\s+(?:vermont residents?|individuals?|people|persons?)', 'medium', 'lower_bound'),

        # Lower confidence patterns (general mentions)
        (r'(\d+(?:,\d+)*)\s+(?:affected|impacted|involved|compromised)', 'low', 'general_affected'),
        (r'total of\s+(\d+(?:,\d+)*)', 'low', 'total_mention'),
        (r'(\d+(?:,\d+)*)\s+(?:vermont residents?)', 'medium', 'vermont_residents'),

        # Very specific Vermont AG patterns from actual PDFs
        (r'(\d+(?:,\d+)*)\s+(?:individuals?|people)\s+in vermont', 'high', 'vt_ag_in_vermont'),
        (r'vermont\s+(?:residents?|individuals?)\s*:?\s*(\d+(?:,\d+)*)', 'high', 'vt_ag_vermont_count'),
    ]

    for pattern, confidence, method in patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            try:
                count = int(match.group(1).replace(',', ''))
                # Skip unrealistic numbers (too small or too large)
                if 10 <= count <= 100000000:  # Reasonable range for breach notifications
                    # Additional validation: skip if the number appears in a date context
                    full_match = match.group(0)
                    if not re.search(r'\b(?:19|20)\d{2}\b', full_match):  # Not a year
                        result['count'] = count
                        result['raw_text'] = full_match
                        result['confidence'] = confidence
                        result['extraction_method'] = method
                        logger.debug(f"Found affected individuals: {count} using method {method}")
                        return result  # Return first valid match with highest confidence
            except ValueError:
                continue

    return result

def analyze_pdf_content(pdf_url: str) -> dict:
    """
    Enhanced PDF content analysis for comprehensive breach details (Tier 3).
    Extracts affected individuals, data types, and incident details from Vermont AG PDFs.
    """
    try:
        logger.info(f"Analyzing Vermont AG PDF: {pdf_url}")

        pdf_analysis = {
            'pdf_analyzed': True,
            'pdf_url': pdf_url,
            'affected_individuals': None,
            'what_information_involved': {},
            'raw_text': '',
            'extraction_confidence': 'low'  # Track confidence in extraction
        }

        # Extract PDF content using local libraries (PyPDF2 and pdfplumber)
        try:
            # Add rate limiting delay before PDF request
            rate_limit_delay()

            # Download PDF content
            response = requests.get(pdf_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                # Try to extract text from PDF using PyPDF2 first
                try:
                    import PyPDF2
                    pdf_file = io.BytesIO(response.content)
                    pdf_reader = PyPDF2.PdfReader(pdf_file)

                    text_content = ""
                    for page in pdf_reader.pages:
                        text_content += page.extract_text() + "\n"

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
                        logger.error("Neither PyPDF2 nor pdfplumber available for PDF parsing")
                        raise Exception("No PDF parsing libraries available")

                    except Exception as pdfplumber_error:
                        logger.debug(f"pdfplumber extraction failed: {pdfplumber_error}")
                        # Last resort: try to extract any readable text from response
                        fallback_text = clean_text_for_database(response.text)
                        content = fallback_text.lower()
                        pdf_analysis['raw_text'] = fallback_text[:1000]  # Store sample
                        pdf_analysis['extraction_confidence'] = 'low'
                        logger.warning(f"Using low-confidence text extraction for {pdf_url}")
            else:
                raise Exception(f"HTTP request failed: {response.status_code}")

            # Enhanced affected individuals extraction
            pdf_analysis['affected_individuals'] = extract_affected_individuals_from_pdf(content)

            # Extract "What information was involved?" section
            pdf_analysis['what_information_involved'] = extract_what_information_involved(content)

        except Exception as e:
            logger.warning(f"Could not extract PDF content from {pdf_url}: {e}")
            pdf_analysis['extraction_confidence'] = 'failed'
            pdf_analysis['error'] = str(e)

        return pdf_analysis

    except Exception as e:
        logger.error(f"Failed to analyze PDF {pdf_url}: {e}")
        return {
            'pdf_analyzed': False,
            'pdf_url': pdf_url,
            'error': str(e),
            'extraction_confidence': 'failed'
        }

def fetch_breach_listing_data() -> list:
    """
    Fetch breach data from the Vermont AG listing page (Tier 1 - Portal Raw Data).
    Returns list of breach records with basic information extracted from page titles.
    """
    logger.info("Fetching Vermont AG breach data from listing page...")

    breach_records = []
    page = 0  # Vermont AG pagination starts at page 0
    max_pages = 9   # 0-9 = 10 pages total, reasonable limit for GitHub Actions

    while page <= max_pages:
        try:
            # Construct URL with pagination (Vermont AG starts at page=0)
            url = f"{VERMONT_AG_BREACH_URL}?page={page}"
            logger.info(f"Fetching page {page}: {url}")

            response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find breach notice links in the listing
            # Vermont AG uses a specific structure with individual breach notice pages
            breach_links = []

            # Look for links to individual breach notices
            # Vermont AG uses /document/ URLs with titles like "YYYY-MM-DD Organization Name Data Breach Notice to Consumers"
            for link in soup.find_all('a', href=True):
                href = link['href']
                title = link.get_text(strip=True)

                # Vermont AG breach notices follow pattern: href starts with /document/ and title matches date pattern
                if (href.startswith('/document/') and
                    re.match(r'^\d{4}-\d{2}-\d{2}.*data\s+breach\s+notice', title, re.IGNORECASE)):
                    full_url = urljoin(VERMONT_AG_BREACH_URL, href)
                    breach_links.append({
                        'url': full_url,
                        'title': title,
                        'href': href
                    })

            if not breach_links:
                logger.info(f"No breach notices found on page {page}. Stopping pagination.")
                break

            logger.info(f"Found {len(breach_links)} breach notices on page {page}")

            # Process each breach notice link
            for link_data in breach_links:
                try:
                    title = link_data['title']
                    url = link_data['url']

                    # Extract organization name and date from title
                    organization_name = parse_organization_name_from_title(title)
                    reported_date = parse_date_from_title(title)

                    if not organization_name or not reported_date:
                        logger.warning(f"Skipping breach notice due to missing data: title='{title}'")
                        continue

                    # Check date filtering
                    if not should_process_breach(reported_date):
                        logger.debug(f"Skipping {organization_name} ({reported_date}) - outside date filter")
                        continue

                    # Generate incident UID for deduplication
                    incident_uid = generate_incident_uid(organization_name, reported_date)

                    # Create standardized breach record (Tier 1)
                    breach_record = {
                        'organization_name': organization_name,
                        'reported_date': reported_date,
                        'page_url': url,
                        'page_title': title,
                        'incident_uid': incident_uid,
                        'raw_listing_data': {
                            'original_title': title,
                            'page_url': url,
                            'href': link_data['href'],
                            'page_number': page
                        }
                    }

                    breach_records.append(breach_record)
                    logger.debug(f"Added breach record: {organization_name} ({reported_date})")

                except Exception as e:
                    logger.error(f"Error processing breach link: {link_data}. Error: {e}")
                    continue

            # Add rate limiting between pages
            if page < max_pages:
                rate_limit_delay()

            page += 1

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching page {page}: {e}")
            break
        except Exception as e:
            logger.error(f"Unexpected error processing page {page}: {e}")
            break

    logger.info(f"Completed breach listing fetch. Found {len(breach_records)} breach records.")
    return breach_records

def enhance_breach_record(breach_record: dict) -> dict:
    """
    Enhance a breach record with individual page data and PDF URL (Tier 2).
    """
    try:
        page_url = breach_record['page_url']
        logger.debug(f"Enhancing breach record for {breach_record['organization_name']}: {page_url}")

        # Add rate limiting
        rate_limit_delay()

        # Fetch individual breach notice page
        response = requests.get(page_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract PDF URL from the individual page
        pdf_url = None
        pdf_size = None

        # Look for PDF download links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.endswith('.pdf') or 'pdf' in href.lower():
                pdf_url = urljoin(page_url, href)

                # Try to extract file size if mentioned
                link_text = link.get_text(strip=True)
                size_match = re.search(r'\(([^)]*(?:kb|mb|gb))\)', link_text, re.IGNORECASE)
                if size_match:
                    pdf_size = size_match.group(1)
                break

        # Enhanced breach record with Tier 2 data
        enhanced_record = breach_record.copy()
        enhanced_record['tier_2_enhanced'] = {
            'enhancement_attempted': True,
            'detail_page_scraped': True,
            'pdf_url': pdf_url,
            'pdf_size': pdf_size,
            'detail_page_data': {
                'page_content_sample': soup.get_text()[:500] if soup else None,
                'pdf_found': pdf_url is not None
            }
        }

        if not pdf_url:
            enhanced_record['tier_2_enhanced']['enhancement_errors'] = ['No PDF URL found on detail page']
            logger.warning(f"No PDF URL found for {breach_record['organization_name']}")

        return enhanced_record

    except Exception as e:
        logger.error(f"Error enhancing breach record for {breach_record['organization_name']}: {e}")
        # Return original record with error information
        enhanced_record = breach_record.copy()
        enhanced_record['tier_2_enhanced'] = {
            'enhancement_attempted': True,
            'detail_page_scraped': False,
            'enhancement_errors': [str(e)]
        }
        return enhanced_record

def process_vermont_ag_breaches():
    """
    Main processing function implementing 3-tier data structure for Vermont AG breaches.
    """
    logger.info("Starting Vermont AG Data Security Breach processing...")
    logger.info(f"Processing mode: {PROCESSING_MODE}")
    logger.info(f"Date filter: {FILTER_FROM_DATE}")

    # Initialize Supabase client
    try:
        supabase_client = SupabaseClient()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}. Ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set.")
        return

    # Tier 1: Fetch breach listing data
    breach_records = fetch_breach_listing_data()
    if not breach_records:
        logger.warning("No breach records found. Exiting.")
        return

    total_processed = 0
    total_inserted = 0
    total_skipped = 0

    for breach_record in breach_records:
        try:
            total_processed += 1
            organization_name = breach_record['organization_name']
            reported_date = breach_record['reported_date']

            logger.info(f"Processing breach {total_processed}/{len(breach_records)}: {organization_name} ({reported_date})")

            # Check if record already exists
            existing_status = supabase_client.get_item_enhancement_status(breach_record['page_url'])
            if existing_status['exists']:
                logger.info(f"Breach record already exists for {organization_name}. Skipping.")
                total_skipped += 1
                continue

            # Tier 2: Enhanced processing (if mode allows)
            if PROCESSING_MODE in ['ENHANCED', 'FULL']:
                breach_record = enhance_breach_record(breach_record)

            # Tier 3: PDF analysis (if mode allows and PDF available)
            pdf_analysis_results = []
            if PROCESSING_MODE in ['ENHANCED', 'FULL']:  # Do basic PDF analysis in ENHANCED mode too
                tier_2_data = breach_record.get('tier_2_enhanced', {})
                pdf_url = tier_2_data.get('pdf_url')

                if pdf_url:
                    logger.info(f"Performing PDF analysis for {organization_name}")
                    pdf_analysis = analyze_pdf_content(pdf_url)
                    pdf_analysis_results.append(pdf_analysis)
                else:
                    logger.warning(f"No PDF URL available for analysis of {organization_name}")

            # Prepare data for Supabase insertion
            summary_text = f"Data security breach notification for {organization_name}."

            # Extract affected individuals from PDF analysis if available
            affected_individuals = None
            what_was_leaked = None
            full_content = None

            if pdf_analysis_results:
                for pdf_analysis in pdf_analysis_results:
                    if pdf_analysis.get('pdf_analyzed'):
                        # Extract affected individuals
                        individuals_data = pdf_analysis.get('affected_individuals', {})
                        if individuals_data and individuals_data.get('count'):
                            affected_individuals = individuals_data['count']

                        # Extract what information was involved
                        info_data = pdf_analysis.get('what_information_involved', {})
                        if info_data and info_data.get('what_information_involved_text'):
                            what_was_leaked = info_data['what_information_involved_text']

                        # Store PDF content sample
                        if pdf_analysis.get('raw_text'):
                            full_content = pdf_analysis['raw_text']

                        break  # Use first successful PDF analysis

            # Build comprehensive raw_data_json
            raw_data_json = {
                'tier_1_listing': breach_record.get('raw_listing_data', {}),
                'tier_2_enhanced': breach_record.get('tier_2_enhanced', {}),
                'tier_3_pdf_analysis': pdf_analysis_results,
                'processing_mode': PROCESSING_MODE,
                'date_filter_applied': FILTER_FROM_DATE,
                'incident_uid': breach_record['incident_uid']
            }

            # Get PDF URL for notice_document_url field
            notice_document_url = None
            if breach_record.get('tier_2_enhanced', {}).get('pdf_url'):
                notice_document_url = breach_record['tier_2_enhanced']['pdf_url']

            # Prepare tags
            year = reported_date.split('-')[0] if reported_date else 'unknown'
            tags = ["vermont_ag", "vt_ag", f"year_{year}"]

            # Insert into Supabase
            item_data = {
                "source_id": SOURCE_ID_VERMONT_AG,
                "item_url": breach_record['page_url'],
                "title": organization_name,
                "publication_date": reported_date,
                "reported_date": reported_date,
                "summary_text": summary_text,
                "full_content": full_content,
                "raw_data_json": raw_data_json,
                "tags_keywords": tags,
                "affected_individuals": affected_individuals,
                "notice_document_url": notice_document_url,
                "what_was_leaked": what_was_leaked
            }

            insert_response = supabase_client.insert_item(**item_data)
            if insert_response:
                logger.info(f"Successfully inserted breach record for {organization_name}")
                total_inserted += 1
            else:
                logger.error(f"Failed to insert breach record for {organization_name}")
                total_skipped += 1

        except Exception as e:
            logger.error(f"Error processing breach record for {breach_record.get('organization_name', 'Unknown')}: {e}", exc_info=True)
            total_skipped += 1

    logger.info(f"Finished processing Vermont AG breaches. Total processed: {total_processed}, Inserted: {total_inserted}, Skipped: {total_skipped}")

if __name__ == "__main__":
    logger.info("Vermont AG Data Security Breach Scraper Started")
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set.")
    else:
        logger.info("Supabase environment variables seem to be set.")
        process_vermont_ag_breaches()
        
    logger.info("Vermont AG Data Security Breach Scraper Finished")
